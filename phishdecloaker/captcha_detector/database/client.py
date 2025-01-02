from __future__ import annotations
import os
import uuid
import json
from collections import defaultdict
from typing import (
    Sequence,
    Union,
)

import numpy as np
import numpy.typing as npt
from qdrant_client import models
from qdrant_client import QdrantClient
from qdrant_client.conversions import common_types as types


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    PAYLOAD_PATH = os.path.join(CURRENT_DIR, "payload.json")
    VECTORS_PATH = os.path.join(CURRENT_DIR, "vectors.npy")
    DATABASE_URL = os.getenv("DATABASE_URL", "http://localhost:6333")


class Client:
    def __init__(
        self,
        url: str = Config.DATABASE_URL,
        vector_size: int = 512,
        vector_distance: str = "Cosine",
    ) -> None:
        self.collection = "captchas"
        self.vector_size = vector_size
        self.vector_distance = vector_distance
        self.client = QdrantClient(url=url)
        self.thresholds = defaultdict(
            lambda: 0.5,
            {
                "text_2": 0.75,
                "text_3": 0.70,
                "text_4": 0.50,
                "text_5": 0.70,
                "text_6": 0.25,
                "hcaptcha_checkbox": 0.75,
                "recaptchav2_checkbox": 0.65,
                "hcaptcha": 0.80,
                "recaptchav2": 0.80,
                "geetest_checkbox": 0.50,
                "geetest_click_word": 0.55,
                "geetest_click_icon": 0.40,
                "geetest_click_phrase": 0.60,
                "geetest_slide_puzzle": 0.80,
                "geetest_game_playing": 0.85,
                "geetest_game_playing2": 0.80,
                "geetest_select": 0.65,
                "press_and_hold": 0.65,
            },
        )

    def reset(self) -> None:
        """Delete and recreate collection in its initial state."""
        self.client.recreate_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(
                size=self.vector_size, distance=self.vector_distance
            ),
        )

        payload = open(os.path.join(Config.CURRENT_DIR, Config.PAYLOAD_PATH))
        payload = map(json.loads, payload)
        vectors = np.load(os.path.join(Config.CURRENT_DIR, Config.VECTORS_PATH))
        ids = [str(uuid.uuid4()) for _ in range(vectors.shape[0])]

        self.client.upload_collection(
            collection_name=self.collection, vectors=vectors, payload=payload, ids=ids
        )

    def insert(self, payloads: list[dict], vectors: list[npt.NDArray]) -> None:
        """
        Insert points into collection. If id exists, perform update.

        Args:
            payloads: list of payload dicts.
            vectors: list of vector embeddings.
        """
        assert len(payloads) == len(vectors)
        self.client.upsert(
            self.collection,
            points=[
                models.PointStruct(
                    id=str(uuid.uuid4()), vector=vector.tolist(), payload=payload
                )
                for payload, vector in zip(payloads, vectors)
            ],
        )

    def delete(self, ids: list) -> None:
        """
        Delete points from collection by ids.

        Args:
            ids: list of point UUIDs.
        """
        self.client.delete(
            self.collection, points_selector=models.PointIdsList(points=ids)
        )

    def get_points_by_type(
        self, limit: int, type: str, offset: str = None
    ) -> tuple[list[str], str]:
        """
        Get points belonging to a CAPTCHA type.

        Args:
            limit: How many points to return.
            type: Type of CAPTCHA.
            offset: Skip points with ids less than given offset.

        Returns:
            (list[str]) List of point ids belonging to type.
            (str) Next point offset.
        """
        results, next_offset = self.client.scroll(
            self.collection,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="type", match=models.MatchValue(value=type)
                    )
                ]
            ),
            limit=limit,
            offset=offset,
        )
        results = [result.id for result in results]
        return results, next_offset

    def search(
        self,
        query: Union[
            types.NumpyArray,
            Sequence[float],
            tuple[str, list[float]],
            types.NamedVector,
        ],
        limit: int = 1,
        threshold: float = 0.3,
    ) -> list[str]:
        """
        Search vector database for similarities given query vector.

        Args:
            query: Search for vectors similar to this.
            limit: Top-k candidates to return.
            threshold: Minimal score threshold for the candidates.

        Returns:
            (list[str]) List of possible CAPTCHA types.
        """
        candidates = self.client.search(
            collection_name=self.collection,
            query_vector=query,
            limit=limit,
            score_threshold=threshold,
        )

        for candidate in candidates:
            score: float = candidate.score
            type: str = candidate.payload["type"]
            if score >= self.thresholds[type]:
                return type


client = Client()

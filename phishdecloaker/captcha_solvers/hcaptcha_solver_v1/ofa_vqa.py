from __future__ import annotations

import os
import re
import sys

import numpy as np
import torch
from fairseq import checkpoint_utils, options, tasks, utils
from fairseq.dataclass.utils import convert_namespace_to_omegaconf
from torchvision import transforms


class Config:
    CURRENT_DIR = os.path.dirname(__file__)
    OFA_DIR = os.path.join(CURRENT_DIR, "OFA")
    BPE_DIR = os.path.join(OFA_DIR, "utils", "BPE")
    MODEL_PATH = os.path.join(OFA_DIR, "checkpoints", "vqa_base_best.pt")


sys.path += [Config.OFA_DIR]

from PIL import Image
from tasks.mm_tasks.vqa_gen import VqaGenTask
from utils.zero_shot_utils import zero_shot_step


# Normalize the question
def pre_question(question, max_ques_words):
    question = question.lower().lstrip(",.!?*#:;~").replace("-", " ").replace("/", " ")
    question = re.sub(
        r"\s{2,}",
        " ",
        question,
    )
    question = question.rstrip("\n")
    question = question.strip(" ")
    # truncate question
    question_words = question.split(" ")
    if len(question_words) > max_ques_words:
        question = " ".join(question_words[:max_ques_words])
    return question


# Function to turn FP32 to FP16
def apply_half(t):
    if t.dtype is torch.float32:
        return t.to(dtype=torch.half)
    return t


class OfaVqa:
    def __init__(self):
        # Register VQA task
        tasks.register_task("vqa_gen", VqaGenTask)

        # turn on cuda if GPU is available
        self.use_cuda = torch.cuda.is_available()
        # use fp16 only when GPU is available
        self.use_fp16 = False

        # specify some options for evaluation
        self.parser = options.get_generation_parser()
        self.input_args = [
            "",
            "--task=vqa_gen",
            "--beam=100",
            "--unnormalized",
            f"--path={Config.MODEL_PATH}",
            f"--bpe-dir={Config.BPE_DIR}",
        ]
        self.args = options.parse_args_and_arch(self.parser, self.input_args)
        self.cfg = convert_namespace_to_omegaconf(self.args)

        # Load pretrained ckpt & config
        self.task = tasks.setup_task(self.cfg.task)
        self.models, self.cfg = checkpoint_utils.load_model_ensemble(
            utils.split_paths(self.cfg.common_eval.path), task=self.task
        )

        device = torch.device("cuda" if self.use_cuda else "cpu")

        # Move models to GPU
        for model in self.models:
            model.eval()
            if self.use_fp16:
                model.half()
            if (
                self.use_cuda
                and not self.cfg.distributed_training.pipeline_model_parallel
            ):
                model.to(device)
            model.prepare_for_inference_(self.cfg)

        # Initialize generator
        self.generator = self.task.build_generator(self.models, self.cfg.generation)
        self.mean = [0.5, 0.5, 0.5]
        self.std = [0.5, 0.5, 0.5]

        self.patch_resize_transform = transforms.Compose(
            [
                lambda image: image.convert("RGB"),
                transforms.Resize(
                    (self.cfg.task.patch_image_size, self.cfg.task.patch_image_size),
                    interpolation=transforms.InterpolationMode.BICUBIC,
                ),
                transforms.ToTensor(),
                transforms.Normalize(mean=self.mean, std=self.std),
            ]
        )

        # Text preprocess
        self.bos_item = torch.LongTensor([self.task.src_dict.bos()])
        self.eos_item = torch.LongTensor([self.task.src_dict.eos()])
        self.pad_idx = self.task.src_dict.pad()

    def encode_text(self, text, length=None, append_bos=False, append_eos=False):
        s = self.task.tgt_dict.encode_line(
            line=self.task.bpe.encode(text), add_if_not_exist=False, append_eos=False
        ).long()
        if length is not None:
            s = s[:length]
        if append_bos:
            s = torch.cat([self.bos_item, s])
        if append_eos:
            s = torch.cat([s, self.eos_item])
        return s

    # Construct input for open-domain VQA task
    def construct_sample(self, image: Image, question: str):
        patch_image = self.patch_resize_transform(image).unsqueeze(0)
        patch_mask = torch.tensor([True])

        question = pre_question(question, self.task.cfg.max_src_length)
        question = question + "?" if not question.endswith("?") else question
        src_text = self.encode_text(
            " {}".format(question), append_bos=True, append_eos=True
        ).unsqueeze(0)

        src_length = torch.LongTensor(
            [s.ne(self.pad_idx).long().sum() for s in src_text]
        )
        ref_dict = np.array([{"yes": 1.0}])  # just placeholder
        sample = {
            "id": np.array(["42"]),
            "net_input": {
                "src_tokens": src_text,
                "src_lengths": src_length,
                "patch_images": patch_image,
                "patch_masks": patch_mask,
            },
            "ref_dict": ref_dict,
        }
        return sample

    def answer_question(self, image, question):
        sample = self.construct_sample(image, question)
        sample = (
            utils.move_to_cuda(sample, device=torch.device("cuda"))
            if self.use_cuda
            else sample
        )
        sample = utils.apply_to_sample(apply_half, sample) if self.use_fp16 else sample

        with torch.no_grad():
            result, _ = zero_shot_step(self.task, self.generator, self.models, sample)

        return result[0]["answer"]

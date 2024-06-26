"""
Reference:
    "Learning Open-World Object Proposals without Learning to Classify",
        Aug 2021. https://arxiv.org/abs/2108.06753
        Dahun Kim, Tsung-Yi Lin, Anelia Angelova, In So Kweon and Weicheng Kuo
"""

img_norm_cfg = dict(
    mean=[123.675, 116.28, 103.53], std=[58.395, 57.12, 57.375], to_rgb=True
)
test_pipeline = [
    dict(type="LoadImageFromFile"),
    dict(
        type="MultiScaleFlipAug",
        scale_factor=1.0,
        flip=False,
        transforms=[
            dict(type="Resize"),
            dict(type="RandomFlip", flip_ratio=0.0),
            dict(type="Normalize", **img_norm_cfg),
            dict(type="Pad", size_divisor=32),
            dict(type="ImageToTensor", keys=["img"]),
            dict(type="Collect", keys=["img"]),
        ],
    ),
]
data = dict(
    samples_per_gpu=2,
    workers_per_gpu=2,
    train=dict(
        type="CocoSplitDataset",
        ann_file="/kaggle/input/captcha-webpage-dataset-3/train.json",
        img_prefix="/kaggle/input/captcha-webpage-dataset-3/images/images/",
        pipeline=[
            dict(type="LoadImageFromFile"),
            dict(type="LoadAnnotations", with_bbox=True),
            dict(type="RandomFlip", flip_ratio=0.0),
            dict(
                type="Normalize",
                mean=[123.675, 116.28, 103.53],
                std=[58.395, 57.12, 57.375],
                to_rgb=True,
            ),
            dict(type="Pad", size_divisor=32),
            dict(type="DefaultFormatBundle"),
            dict(type="Collect", keys=["img", "gt_bboxes", "gt_labels"]),
        ],
        is_class_agnostic=True,
        train_class="voc",
        eval_class="nonvoc",
    ),
    val=dict(
        type="CocoSplitDataset",
        ann_file="/kaggle/input/captcha-webpage-dataset-3/test.json",
        img_prefix="/kaggle/input/captcha-webpage-dataset-3/images/images/",
        pipeline=[
            dict(type="LoadImageFromFile"),
            dict(type="RandomFlip", flip_ratio=0.0),
            dict(
                type="Normalize",
                mean=[123.675, 116.28, 103.53],
                std=[58.395, 57.12, 57.375],
                to_rgb=True,
            ),
            dict(type="Pad", size_divisor=32),
            dict(type="ImageToTensor", keys=["img"]),
            dict(type="Collect", keys=["img"]),
        ],
        is_class_agnostic=True,
        train_class="voc",
        eval_class="nonvoc",
    ),
    test=dict(
        type="CocoSplitDataset",
        ann_file="/kaggle/input/captcha-webpage-dataset-3/test.json",
        img_prefix="/kaggle/input/captcha-webpage-dataset-3/images/images/",
        pipeline=[
            dict(type="LoadImageFromFile"),
            dict(type="RandomFlip", flip_ratio=0.0),
            dict(
                type="Normalize",
                mean=[123.675, 116.28, 103.53],
                std=[58.395, 57.12, 57.375],
                to_rgb=True,
            ),
            dict(type="Pad", size_divisor=32),
            dict(type="ImageToTensor", keys=["img"]),
            dict(type="Collect", keys=["img"]),
        ],
        is_class_agnostic=True,
        train_class="voc",
        eval_class="nonvoc",
    ),
)
model = dict(
    type="FasterRCNN",
    pretrained="torchvision://resnet50",
    backbone=dict(
        type="ResNet",
        depth=50,
        num_stages=4,
        out_indices=(0, 1, 2, 3),
        frozen_stages=1,
        norm_cfg=dict(type="BN", requires_grad=True),
        norm_eval=True,
        style="pytorch",
    ),
    neck=dict(
        type="FPN", in_channels=[256, 512, 1024, 2048], out_channels=256, num_outs=5
    ),
    rpn_head=dict(
        type="OlnRPNHead",
        in_channels=256,
        feat_channels=256,
        anchor_generator=dict(
            type="AnchorGenerator", scales=[8], ratios=[1.0], strides=[4, 8, 16, 32, 64]
        ),
        bbox_coder=dict(type="TBLRBBoxCoder", normalizer=1.0),
        loss_cls=dict(type="CrossEntropyLoss", use_sigmoid=True, loss_weight=0.0),
        reg_decoded_bbox=True,
        loss_bbox=dict(type="IoULoss", linear=True, loss_weight=10.0),
        objectness_type="Centerness",
        loss_objectness=dict(type="L1Loss", loss_weight=1.0),
    ),
    roi_head=dict(
        type="OlnRoIHead",
        bbox_roi_extractor=dict(
            type="SingleRoIExtractor",
            roi_layer=dict(type="RoIAlign", output_size=7, sampling_ratio=0),
            out_channels=256,
            featmap_strides=[4, 8, 16, 32],
        ),
        bbox_head=dict(
            type="Shared2FCBBoxScoreHead",
            in_channels=256,
            fc_out_channels=1024,
            roi_feat_size=7,
            num_classes=1,
            bbox_coder=dict(
                type="DeltaXYWHBBoxCoder",
                target_means=[0.0, 0.0, 0.0, 0.0],
                target_stds=[0.1, 0.1, 0.2, 0.2],
            ),
            reg_class_agnostic=False,
            loss_cls=dict(type="CrossEntropyLoss", use_sigmoid=False, loss_weight=0.0),
            loss_bbox=dict(type="L1Loss", loss_weight=1.0),
            bbox_score_type="BoxIoU",
            loss_bbox_score=dict(type="L1Loss", loss_weight=1.0),
        ),
    ),
    train_cfg=dict(
        rpn=dict(
            assigner=dict(
                type="MaxIoUAssigner",
                pos_iou_thr=0.7,
                neg_iou_thr=0.3,
                min_pos_iou=0.3,
                ignore_iof_thr=-1,
            ),
            sampler=dict(
                type="RandomSampler",
                num=256,
                pos_fraction=0.5,
                neg_pos_ub=-1,
                add_gt_as_proposals=False,
            ),
            objectness_assigner=dict(
                type="MaxIoUAssigner",
                pos_iou_thr=0.3,
                neg_iou_thr=0.1,
                min_pos_iou=0.3,
                ignore_iof_thr=-1,
            ),
            objectness_sampler=dict(
                type="RandomSampler",
                num=256,
                pos_fraction=1.0,
                neg_pos_ub=-1,
                add_gt_as_proposals=False,
            ),
            allowed_border=0,
            pos_weight=-1,
            debug=False,
        ),
        rpn_proposal=dict(
            nms_across_levels=False,
            nms_pre=2000,
            nms_post=2000,
            max_num=2000,
            nms_thr=0.7,
            min_bbox_size=0,
        ),
        rcnn=dict(
            assigner=dict(
                type="MaxIoUAssigner",
                pos_iou_thr=0.5,
                neg_iou_thr=0.5,
                min_pos_iou=0.5,
                match_low_quality=False,
                ignore_iof_thr=-1,
            ),
            sampler=dict(
                type="RandomSampler",
                num=512,
                pos_fraction=0.25,
                neg_pos_ub=-1,
                add_gt_as_proposals=True,
            ),
            pos_weight=-1,
            debug=False,
        ),
    ),
    test_cfg=dict(
        rpn=dict(
            nms_across_levels=False,
            nms_pre=2000,
            nms_post=2000,
            max_num=2000,
            nms_thr=0.0,
            min_bbox_size=0,
        ),
        rcnn=dict(
            score_thr=0.0, nms=dict(type="nms", iou_threshold=0.7), max_per_img=1500
        ),
    ),
)

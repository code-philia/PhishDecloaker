# CAPTCHA Solver Repository

| CAPTCHA | Solver | Description |
| --- | --- | --- |
| reCAPTCHA v2 | `recaptchav2_solver_v3` | Handles image-based challenges. Uses multimodal large language models (i.e. OpenAI GPT-4V) as the backbone for image recognition and object detection. Prototype tested in field study. | 
| | `recaptchav2_solver_v2` | Exploits audio-based accessbility challenges. Uses a general-purpose speech recognition model (i.e. OpenAI Whisper) as the backbone for audio transcription. Prototype discontinued due to poor scalability (although it has the best solve rate, frequent use will get rate-limited by Google). |
| | `recaptchav2_solver_v1` | Handles image-based challenges. Uses conventional object detection models (i.e. YOLO) as the backbone for object detection. |
| hCaptcha | `hcaptcha_solver_v3` | Handles both binary and area select challenge variants. Uses multimodal large language models (i.e. OpenAI GPT-4V) as the backbone for visual question answering. |
| | `hcaptcha_solver_v2` | Handles both binary and area select challege variant. Uses out-of-shelf (i.e. <a href="https://github.com/QIN2DIM/hcaptcha-challenger" target="_blank">hcaptcha-challenger</a>) solver with an ensemble of fine-tuned binary classifiers and conventional object detection models for visual question answering. |
| | `hcaptcha_solver_v1` | Handles binary challenge variant only. Uses a unified sequence-to-sequence pretrained model (i.e. OFA) fine-tuned on downstream visual question answering tasks. |
| rotation CAPTCHA | `rotation_solver` | Handles Baidu rotation CAPTCHA. Uses a regression model trained on image orientation prediction task. |
| slider CAPTCHA | `slider_solver` | Handles GeeTest, NetEase, and Tencent slider CAPTCHAs. Uses edge detection and template matching to find the position of the puzzle gap given the puzzle piece. Uses easing functions to generate mouse trajectory. |
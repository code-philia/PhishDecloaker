# PhishDecloaker

PhishDecloaker is a hybrid deep-vision system to detect, recognize, and solve diverse CAPTCHAs. The CAPTCHA solving repository currently supports 4 different CAPTCHA types: reCAPTCHA v2, hCaptcha, slide CAPTCHA, rotation CAPTCHA and can be extended to support more CAPTCHA types.

PhishDecloaker is developed as part of the paper: _"PhishDecloaker: Detecting CAPTCHA-cloaked Phishing Websites via Hybrid
Vision-based Interactive Models"_ to capture and study CAPTCHA-cloaked phishing websites, published at [USENIX Security '24](https://www.usenix.org/conference/usenixsecurity24/).

## Technical Details

PhishDecloaker is implemented as a microservice system that continuously monitors domains with newly registered TLS/SSL certificates from CertStream. New domains are added to a queue to be crawled in parallel by distributed crawlers. The crawled content is analyzed for suspicious CAPTCHA-cloaking behavior (i.e., CAPTCHA detection and recognition). CAPTCHA solvers are deployed to interact with live CAPTCHA block pages and reveal the hidden content (i.e., CAPTCHA solving and website decloaking). The data flow of containers in the system are as follows:

### Branch A: CAPTCHA-cloaked Phishing Websites
| Sequence | Description |
| --- | --- |
| certstream → filter | Incoming CertStream domains undergo preliminary keyword-based filtering. |
| filter → queue | Potentially suspicious domains above threshold score are published to both `baseline` and `captcha` queues (see types of crawlers below). |
| queue → crawler | Domains are crawled and their content analyzed. Suspicious CAPTCHA-cloaking behavior is potentially present if all the following checks are passed: <ol><li>A HEAD request was successful, website is alive.</li><li>The "captcha" keyword was intercepted in any network request(s) when loading the site.</li><li>The number of white pixels in the greyscale screenshot of the page is outside the nominal range, indicating a 'blocked' page with a lot of whitespace (see Cloudflare, Forcepoint, or Imperva for examples).</li></ol> Types of crawlers: <ul><li>`baseline`: crawler with all decloaking techniques except CAPTCHA decloaking</li><li>`captcha`: crawler group 6 for field study</li><li>`group`: different crawler groups (1-5) configured for field study</li></ul> | 
| crawler → queue | Crawled domains and their corresponding content are added to the `crawled` queue. |

### Branch B: Other Phishing Websites
| Sequence | Description |
| --- | --- |
| certstream → filter | Incoming CertStream domains undergo preliminary keyword-based filtering. |
| filter → queue | Potentially suspicious domains above threshold score are published to both `baseline` and `captcha` queues (see types of crawlers below). |
| queue → crawler | Domains are crawled and their content analyzed. Suspicious CAPTCHA-cloaking behavior is potentially present if all the following checks are passed: <ol><li>A HEAD request was successful, website is alive.</li><li>The "captcha" keyword was intercepted in any network request(s) when loading the site.</li><li>The number of white pixels in the greyscale screenshot of the page is outside the nominal range, indicating a 'blocked' page with a lot of whitespace (see Cloudflare, Forcepoint, or Imperva for examples).</li></ol> Types of crawlers: <ul><li>`baseline`: crawler with all decloaking techniques except CAPTCHA decloaking</li><li>`captcha`: crawler group 6 for field study</li><li>`group`: different crawler groups (1-5) configured for field study</li></ul> | 
| crawler → queue | Crawled domains and their corresponding content are added to the `crawled` queue. |

## Installation

PhishDecloaker is tested on Ubuntu 20.04 with NVIDIA RTX A4000. Follow these steps to deploy the system:

1. **Clone this repository:**

    ```bash
    git clone https://github.com/code-philia/phishdecloaker
    cd phishdecloaker/phishdecloaker
    ```

2. **Prepare container images**

    There are two options available to prepare container images for PhishDecloaker:

    ***Option A:** Pulling (fastest)*

    Use the following command to pull the necessary Docker images:
    ```bash
    docker compose pull
    ```

    ***Option B:** Building (for development)*

    First, make sure you have downloaded all the resources (i.e., model weights, dependencies) necessary to build containers.

    <details>
    <summary><code>/phishing_detector</code></summary>
    Can be downloaded at: <a href="https://huggingface.co/code-philia/PhishIntention/tree/701a616fafbd05827e0b963dce29e9f187c76a0d">link</a>
    <pre>.<br>└── phishintention<br>    └── src<br>        ├── AWL_detector_utils<br>        │   ├── configs/faster_rcnn_web.yaml<br>        │   └── output/website_lr0.001/model_final.pth<br>        ├── crp_locator_utils<br>        │   └── login_finder<br>        │       ├── configs/faster_rcnn_login_lr0.001_finetune.yaml<br>        │       └── output/lr0.001_finetune/model_final.pth<br>        ├── crp_classifier_utils/output/Increase_resolution_lr0.005/BiT-M-R50x1V2_0.005.pth.tar<br>        ├── OCR_siamese_utils<br>        │       ├── output/targetlist_lr0.01/bit.pth.tar<br>        │       └── demo_downgrade.pth.tar<br>        └── phishpedia_siamese<br>                ├── LOGO_FEATS.npy<br>                ├── LOGO_FILES.npy<br>                ├── expand_targetlist<br>                └── domain_map.pkl</pre>
    </details>

    <details>
    <summary><code>/captcha_detector</code></summary>
    Can be downloaded at: <a href="https://huggingface.co/code-philia/PhishDecloaker/tree/61bb57fe6648d938aa92bfab0a420acdf7027144/captcha_detector">link</a>
    <pre>.<br>├── database<br>│   ├── vectors.npy<br>│   └── payload.json<br>├── detector<br>│   └── oln_detector.pth<br>├── ocr<br>│   ├── craft_mit_25k.pth<br>│   └── zh_sim_g2.pth<br>└── siamese<br>    ├── trunk.ts<br>    └── embedder.ts</pre>
    </details>

    Then, use the following commands to build the Docker images yourself, for instance after you modified the code:
    ```bash
    docker compose build
    ```

## Usage

1. **Install NVIDIA Container Toolkit**

    If you plan to use PhishDecloaker with GPU support, following the instructions [here](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) to install NVIDIA Container Toolkit.

2. **Configure environment variables**

    Create a `.env` file from `.env.example` and fill in the missing values.

    ```python
    # 1. crawler
    # 1.1. Skip domains in this list (separated by '|')
    # 1.2. Skip domains containing any subdomain in this list (separated by '|')
    # 1.3. Skip domains with DOM containing any keyword in this list (separated by '|')
    DOMAIN_WHITELIST="domain1.com|domain2.com"
    SUBDOMAIN_WHITELIST="subdomain1.|subdomain2."
    KEYWORD_WHITELIST="keyword1|keyword2"

    # 2. controller
    # 2.1. VirusTotal API key for checking if a phishing website is 0-day in field study
    VIRUSTOTAL_API_KEY="d3ee0fb7cce1f6948......853a5e2878256c8"

    # 3. captcha_solver
    # 3.1. OpenAI API key (if using LLM-based CAPTCHA solver)
    OPENAI_API_KEY="sk-NzTxWTD......Ssn8W"

    # 2. poller
    # 2.1. unique token that authenticates your bot on the bot API (see https://core.telegram.org/bots/tutorial).
    # 2.2. Telegram bot will receive incoming updates via an outgoing webhook on the server (if using cloudflared, please register WEBHOOK_DOMAIN on cloudflare tunnel).
    # 2.3. Telegram bot will send poll and updates to this group
    TELEGRAM_BOT_TOKEN="6666666666:AAEI_QNXg9O......KOHqkw"
    TELEGRAM_WEBHOOK_URL="https://[WEBHOOK_DOMAIN]/[TELEGRAM_BOT_TOKEN]"
    TELEGRAM_GROUP_ID=123456

    # 3. cloudflared
    # 3.1. Cloudflare tunnelling for telegram polling bot behind private networks without a publicly routable IP address. 
    CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiZTUzODV......WlRaaiJ9"
    ```

2. **Configure docker compose**

    Ensure that your `.env` file created in the previous step is in the same directory as `./docker-compose.yml`.

3. **Start PhishDecloaker**

    Start all containers. The management dashboard can be accessed at the specified `PORT` by providing `DASHBOARD_USERNAME` and `DASHBOARD_PASSWORD`.
    ```bash
    docker compose up
    ```
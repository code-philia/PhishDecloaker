# PhishDecloaker

PhishDecloaker is a hybrid deep-vision system to detect, recognize, and solve diverse CAPTCHAs. The CAPTCHA solving repository currently supports 4 different CAPTCHA types: reCAPTCHA v2, hCaptcha, slide CAPTCHA, rotation CAPTCHA and can be extended to support more CAPTCHA types.

PhishDecloaker is developed as part of the paper: _"PhishDecloaker: Detecting CAPTCHA-cloaked Phishing Websites via Hybrid
Vision-based Interactive Models"_ to capture and study CAPTCHA-cloaked phishing websites, published at [USENIX Security '24](https://www.usenix.org/conference/usenixsecurity24/).

## Technical Details

PhishDecloaker is implemented as a microservice system that continuously monitors domains with newly registered TLS/SSL certificates from CertStream. New domains are added to a queue to be crawled in parallel by distributed crawlers. The crawled content is analyzed for suspicious CAPTCHA-cloaking behavior (i.e., CAPTCHA detection and recognition). CAPTCHA solvers are deployed to interact with live CAPTCHA block pages and reveal the hidden content (i.e., CAPTCHA solving and website decloaking). The data flow of containers in the system are as follows:

### Branch A: CAPTCHA-cloaked Phishing Websites
| <div style="width:150px">Sequence</div> | Description |
| --- | --- |
| certstream → filter | Incoming CertStream domains undergo preliminary keyword-based filtering. |
| filter → queue | Potentially suspicious domains above threshold score are published to `captcha` queue. |
| queue → crawler | Domains are crawled and their content analyzed. Suspicious CAPTCHA-cloaking behavior is potentially present if all the following checks are passed: <ol><li>A HEAD request was successful, website is alive.</li><li>The "captcha" keyword was intercepted in any network request(s) when loading the site.</li><li>The number of white pixels in the greyscale screenshot of the page is outside the nominal range, indicating a 'blocked' page with a lot of whitespace (see Cloudflare, Forcepoint, or Imperva for examples). | 
| crawler → queue | Crawled websites and their corresponding content are added to the `crawled` queue with `CAPTCHA` flag. |
| queue → controller | Controller receives next website in queue. |
| controller ⇄ captcha_detector | If website has `CAPTCHA` flag, controller sends website screenshot for CAPTCHA detection and recognition. Results are sent back to the controller. |
| controller → queue | If CAPTCHA is detected on the website, controller sends website to solver queue based on CAPTCHA type. |
| queue ⇄ solver | CAPTCHA solver loads the website and solves the CAPTCHA challenge. Once the CAPTCHA is solved, the revealed content is added to the `crawled` queue with `CAPTCHA_SOLVED` flag. |
| queue → controller | Controller receives next website in queue. |
| controller ⇄ phishing_detector | If website has `CAPTCHA_SOLVED` flag, controller sends its content to phishing detector for analysis. |
| controller → database | If website is suspected as phishing, controller requests a VirusTotal scan to see if it is 0-day. The scan report and website data are stored in database. |
| controller → poller | Controller signals the Telegram bot, which in turn will notify users to label the suspected phishing website. |

### Branch B: Other Phishing Websites
| <div style="width:150px">Sequence</div> | Description |
| --- | --- |
| certstream → filter | Incoming CertStream domains undergo preliminary keyword-based filtering. |
| filter → queue | Potentially suspicious domains above threshold score are published to `baseline` queue. |
| queue → crawler | Domains are crawled by `baseline` crawler with all decloaking techniques (except CAPTCHA decloaking) enabled. | 
| crawler → queue | Crawled websites and their corresponding content are added to the `crawled` queue with `BASELINE` flag. |
| queue → controller | Controller receives next website in queue. |
| controller ⇄ phishing_detector | If website has `BASELINE` flag, controller sends its content to phishing detector for analysis. |
| controller → queue | If website is suspected as phishing, controller requests a VirusTotal scan to see if it is 0-day and adds the website to `group` queue for group crawling. |
| queue → crawler | Domains are crawled by `group` crawlers, which consists of crawler groups (1-5) with different configurations for field study. |
| crawler → queue | The website, together with the list of website contents as crawled by each group is added to the `crawled` queue with `GROUP` flag. |
| queue → controller | Controller receives next website in queue. |
| controller ⇄ phishing_detector | If website has `GROUP` flag, controller sends the list of website contents to phishing detector for analysis. This is to check which crawler group can decloak the phishing website and reveal its content. |
| controller → database | The scan report and website data are stored in database. |
| controller → poller | Controller signals the Telegram bot, which in turn will notify users to label the suspected phishing website. |

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

    <details>
    <summary><code>(optional) /captcha_solvers/recaptchav2_solver_v 1</code></summary>
    Can be downloaded at: <a href="https://huggingface.co/code-philia/PhishDecloaker/tree/1e912351c15717b20cd954ec541be963df76fb93/captcha_solvers/recaptchav2_solver_v1">link</a>
    <pre>.<br>├── detector_coco<br>│   └── yolov7.weights<br>└── detector_custom<br>    └── yolov3_final.weights</pre>
    </details>

    <details>
    <summary><code>(optional) /captcha_solvers/hcaptcha_solver_v1</code></summary>
    Can be downloaded at: <a href="https://huggingface.co/OFA-Sys/ofa-base-vqa-fairseq-version/tree/da37c4fbd245ef3d908e6424f2c04d445ef6fb03">link</a>
    <pre>.<br>└── OFA<br>    └── checkpoints<br>        └── vqa_base_best.pt</pre>
    </details>

    <details>
    <summary><code>(optional) /captcha_solvers/rotation_solver</code></summary>
    Can be downloaded at: <a href="https://huggingface.co/code-philia/PhishDecloaker/tree/797535eb6b87f5e42c4892019a551d12f8649137/captcha_solvers/rotation_solver">link</a>
    <pre>.<br>└── rotmodel.pth</pre>
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

    # 4. poller
    # 4.1. unique token that authenticates your bot on the bot API (see https://core.telegram.org/bots/tutorial).
    # 4.2. Telegram bot will receive incoming updates via an outgoing webhook on the server (if using cloudflared, please register WEBHOOK_DOMAIN on cloudflare tunnel).
    # 4.3. Telegram bot will send poll and updates to this group
    TELEGRAM_BOT_TOKEN="6666666666:AAEI_QNXg9O......KOHqkw"
    TELEGRAM_WEBHOOK_URL="https://[WEBHOOK_DOMAIN]/[TELEGRAM_BOT_TOKEN]"
    TELEGRAM_GROUP_ID=123456

    # 5. cloudflared
    # 5.1. Cloudflare tunnelling for telegram polling bot behind private networks without a publicly routable IP address. 
    CLOUDFLARE_TUNNEL_TOKEN="eyJhIjoiZTUzODV......WlRaaiJ9"
    ```

2. **Configure docker compose**

    Ensure that your `.env` file created in the previous step is in the same directory as `./docker-compose.yml`.

3. **Start PhishDecloaker**

    Create a shared network and start all containers.
    ```bash
    docker network create phishdecloaker
    docker compose -f docker-compose-main.yml -f docker-compose-solvers.yml up -d
    ```

4. **Monitoring and Visualization**

    The system exposes some services for data visualization and analysis.
    - `database-viewer:8081`: Browse all captured phishing and captcha websites stored in database.
    - `queues:15672`: Monitor the status of all defined queues.

5. **Stop PhishDecloaker**

    Create a shared network and start all containers.
    ```bash
    docker network rm phishdecloaker
    docker compose -f docker-compose-main.yml -f docker-compose-solvers.yml down
    ```
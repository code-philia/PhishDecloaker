const fetch = require('node-fetch');
const crypto = require('crypto');

const verifyReCaptcha = async (body) => {
  const verifyParams = new URLSearchParams();
  verifyParams.append('secret', process.env.RECAPTCHAV2_SECRET_KEY);
  verifyParams.append('response', body["g-recaptcha-response"]);

  let verifyResponse = await fetch("https://www.recaptcha.net/recaptcha/api/siteverify", {
      method: "POST",
      body: verifyParams
  });

  verifyResponse = await verifyResponse.json();

  console.log(verifyResponse);

  return verifyResponse["success"]
}

const verifyHCaptcha = async (body) => {
  const verifyParams = new URLSearchParams();
  verifyParams.append('secret', process.env.HCAPTCHA_SECRET_KEY);
  verifyParams.append('response', body["h-captcha-response"]);

  let verifyResponse = await fetch("https://hcaptcha.com/siteverify", {
      method: "POST",
      body: verifyParams
  });

  verifyResponse = await verifyResponse.json();
  return verifyResponse["success"]
}

const verifySlideCaptcha = async (body) => {
  const secretKey = process.env.SLIDE_SECRET_KEY;
  const lotNumber = body.lotNumber;
  const signToken = crypto.createHmac("sha256", secretKey).update(lotNumber, 'utf8').digest('hex');
  const verifyParams = new URLSearchParams();
  verifyParams.append('lot_number', lotNumber);
  verifyParams.append('captcha_output', body.captchaOutput);
  verifyParams.append('pass_token', body.passToken);
  verifyParams.append('gen_time', body.genTime);
  verifyParams.append('sign_token', signToken);

  const verifyUrl = `http://gcaptcha4.geetest.com/validate?captcha_id=${process.env.SLIDE_SITE_KEY}`;

  let verifyResponse = await fetch(verifyUrl, {
      method: "POST",
      body: verifyParams
  });

  verifyResponse = await verifyResponse.json();

  return verifyResponse.result === "success"
}

const verifyRotateCaptcha = async (body) => {
  const tolerance = 10;
  const angle = parseFloat(decrypt(body.challengeToken));
  return (Math.abs(angle - body.challengeAnswer) <= tolerance);
}

const encrypt = (text) => {
  const algorithm = "aes-256-cbc";
  const iv_length = 16;
  const iv = crypto.randomBytes(iv_length);
  const cipher = crypto.createCipheriv(algorithm, Buffer.from(process.env.ROTATE_SECRET_KEY, 'hex'), iv);
  let encrypted = cipher.update(text);
  encrypted = Buffer.concat([encrypted, cipher.final()]);
  return `${iv.toString('hex')}:${encrypted.toString('hex')}`;
};

const decrypt = (text) => {
  const algorithm = "aes-256-cbc";
  const [iv, encryptedText] = text.split(':').map(part => Buffer.from(part, 'hex'));
  const decipher = crypto.createDecipheriv(algorithm, Buffer.from(process.env.ROTATE_SECRET_KEY, 'hex'), iv);
  let decrypted = decipher.update(encryptedText);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  return decrypted.toString();
};


const verifyCaptcha = {
  "recaptchav2": verifyReCaptcha,
  "hcaptcha": verifyHCaptcha,
  "slide": verifySlideCaptcha,
  "rotate": verifyRotateCaptcha,
  "none": () => true
}

const captchaConfigs = {
  "recaptchav2": { siteKey: process.env.RECAPTCHAV2_SITE_KEY, domain: process.env.RECAPTCHAV2_DOMAIN },
  "hcaptcha": { siteKey: process.env.HCAPTCHA_SITE_KEY, domain: process.env.HCAPTCHA_DOMAIN },
  "slide": { siteKey: process.env.SLIDE_SITE_KEY, domain: process.env.SLIDE_DOMAIN },
  "rotate": { domain: process.env.ROTATE_DOMAIN },
  "none": { domain: process.env.NONE_DOMAIN }
}

module.exports = {
  verifyCaptcha,
  captchaConfigs,
  encrypt,
  decrypt
}
const express = require('express');
const mongoose = require('mongoose');
const jimp = require("jimp");
const router = express.Router();
const Honeypot = require('../models/honeypot.js');
const Fingerprint = require('../models/fingerprint.js');
const Visit = require('../models/visit.js');
const captcha = require('../utils/captcha.js');
const constants = require("../utils/constants.js");
const proxy = require('express-http-proxy');

const phishingKitProxy = proxy(process.env.PHISHING_KIT_URL, { 
    proxyReqPathResolver: function(req) {
        let kitId = req.honeypot.kitId;
        return `/kit${kitId}/`;
    },
    userResDecorator: function(proxyRes, proxyResData, userReq, userRes) {
        return `<base href='/resources/'>` + proxyResData;
    }
});

const phishingKitResourcesProxy = proxy(process.env.PHISHING_KIT_URL, {
    proxyReqPathResolver: function(req) { 
        let kitId = req.honeypot.kitId;
        return `/kit${kitId}/${req.path.slice(11)}`;
    }
});

// Catch all incoming queries
// 1. Extract subdomain
// 2. Query honeypot in DB (honeypot ID = subdomain)
// 3. Mark honeypot as accessed
router.use(async (req, res, next) => {
    let honeypotId = req.hostname.split(".")[0];

    if (req.path != "/beacon" && mongoose.isValidObjectId(honeypotId)) {
        let honeypot = await Honeypot.findByIdAndUpdate(honeypotId, { 
            'accessed': true, 
            $min: {'accessedAt' : (Date.now())}
        });

        if (honeypot) {
            req.honeypot = honeypot;
            req.honeypotId = honeypotId;
        }
    }
    
    next();
});

// Load cloaking page
router.get('/', async (req, res, next) => {
    if (req.honeypot) {
        let captchaType = req.honeypot.captchaType;
        let sessionId = new mongoose.Types.ObjectId();
        let proxyId = req.query.id;
        await Visit.create({ honeypotId: req.honeypotId });

        if (captchaType == "none") {
            return phishingKitProxy(req, res, next);
        } else {
            return res.render(`cloaking/${captchaType}`, {
                sessionId: sessionId,
                proxyId: proxyId,
                ...captcha.captchaConfigs[captchaType]
            });  
        }
    }

    next();
});

// Submit CAPTCHA challenge
router.post('/', async (req, res, next) => {
    let captchaType = req.body.captchaType;
    let isVerified = await captcha.verifyCaptcha[captchaType](req.body);

    if (isVerified && req.honeypotId) {
        await Honeypot.findByIdAndUpdate(req.honeypotId, { 
            'solved': true, 
            $min: {'solvedAt' : (Date.now())}
        });

        return phishingKitProxy(req, res, next);
    } else {
        let redirectUrl = constants.redirectList[Math.floor(Math.random() * constants.redirectList.length)];
        res.status(301).redirect(redirectUrl);
    }
});

// For a subset of visitors with JS rendering enabled
router.post('/beacon', async (req, res, next) => {
    req.body = JSON.parse(req.body);
    let fingerprint = req.body;
    await Fingerprint.create(fingerprint);
    res.status(200).send("ok"); 
});

// Serve rotate CAPTCHA
router.get('/captcha/rotate', async (req, res, next) => {
    setTimeout((async () => {
        let imageWidth = 400;
        let imageIndex = Math.floor(Math.random() * (constants.imageList.length))
        let image = await jimp.read(Buffer.from(constants.imageList[imageIndex], "base64"));
        let rotateAngle = Math.random() * (315 - 45) + 45;
        let newWidth = Math.trunc(2 * Math.sqrt(Math.pow(imageWidth, 2) / 8));
        let newOffset = Math.trunc((imageWidth - newWidth) / 2);
    
        image.rotate(rotateAngle, false);
        image.crop(newOffset, newOffset, newWidth, newWidth);
        let im64 = await image.getBase64Async(jimp.MIME_JPEG);
        let token = captcha.encrypt(rotateAngle.toString());
    
        res.json({ challengeImage: im64, challengeToken: token });
    }), Math.random() * (3000))
})

router.get('/*', async (req, res, next) => {
    if (req.honeypotId) {
        return phishingKitResourcesProxy(req, res, next);
    }

    next();
});

module.exports = router;
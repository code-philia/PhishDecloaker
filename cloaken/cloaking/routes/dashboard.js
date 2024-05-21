const express = require('express');
const basicAuth = require('express-basic-auth');
const parser = require("@json2csv/node");
const router = express.Router();
const ape = require('../utils/ape.js');
const captcha = require('../utils/captcha.js')
const Honeypot = require('../models/honeypot.js');
const Fingerprint = require('../models/fingerprint.js');
const Visit = require('../models/visit.js');

const apeTypes = Object.keys(ape.toApe);
const captchaTypes = Object.keys(captcha.verifyCaptcha);

router.use(basicAuth({
    challenge: true,
    users: {
        [process.env.DASHBOARD_USERNAME]: process.env.DASHBOARD_PASSWORD
    }
}));

router.get('/', async (req, res, next) => {
    return res.render('dashboard', {
        captchaTypes: captchaTypes,
        apeTypes: apeTypes
    });
});

router.post('/honeypots', async (req, res) => {
    let startKitId = parseInt(req.body.startKitId);
    let endKitId = parseInt(req.body.endKitId);
    let captchaType = req.body.captchaType;
    let apeType = req.body.apeType;

    let honeypots = [];
    for (var i = startKitId; i <= endKitId; i++) {
        var honeypot = {
            captchaType,
            apeType,
            kitId: i,
            domain: captcha.captchaConfigs[captchaType].domain
        }
        honeypots.push(honeypot);
    }
    await Honeypot.insertMany(honeypots);
    return res.redirect('/');
});

router.get('/honeypots', async (req, res, next) => {
    let apeType = req.query.apeType;
    let captchaType = req.query.captchaType;
    let honeypots = await Honeypot.find({ apeType, captchaType }).sort({ kitId: 1 }).lean();
    return res.json({ honeypots });
})

router.post('/honeypots/delete', async (req, res) => {
    let honeypotIds = req.body.honeypotIds || [];

    console.log(honeypotIds);

    await Honeypot.deleteMany({ _id: { $in: honeypotIds } })
    return res.redirect('/');
});

router.post('/honeypots/sent', async (req, res) => {
    let honeypotIds = req.body.honeypotIds || [];
    await Honeypot.updateMany({ _id: { $in: honeypotIds } }, {
        'sent': true, 
        $min: {'sentAt' : (Date.now())}    
    });
    return res.redirect('/');
});

router.get('/honeypots/export', async (req, res) => {
    let honeypots = await Honeypot.find({}).lean();
    let fields = ['_id', 'apeType', 'captchaType', 'sent', 'accessed', 'solved', 'sentAt', 'accessedAt', 'solvedAt', 'visits']
    let asyncParser = new parser.AsyncParser({ fields });
    let csv = await asyncParser.parse(honeypots).promise();
    res.attachment('honeypots.csv').send(csv)
});

router.get('/fingerprints/export', async (req, res) => {
    let fingerprints = await Fingerprint.find({}).lean();
    let fields = ['_id', 'visitorId', 'honeypotId', 'createdAt']
    let asyncParser = new parser.AsyncParser({ fields });
    let csv = await asyncParser.parse(fingerprints).promise();
    res.attachment('fingerprints.csv').send(csv)
});

router.get('/visits/export', async (req, res) => {
    let visits = await Visit.find({}).lean();
    let fields = ['_id', 'honeypotId', 'createdAt']
    let asyncParser = new parser.AsyncParser({ fields });
    let csv = await asyncParser.parse(visits).promise();
    res.attachment('visits.csv').send(csv)
});

module.exports = router;
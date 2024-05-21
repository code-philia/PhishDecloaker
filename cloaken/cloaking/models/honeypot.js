const mongoose = require('mongoose');

const HoneypotSchema = new mongoose.Schema({
    captchaType: {
        type: String,
        enum: ["none", "recaptchav2", "hcaptcha", "slide", "rotate"],
        required: true
    },
    apeType: {
        type: String,
        enum: ["none", "virustotal", "googleSafeBrowsing", "microsoftDefender"],
        required: true 
    },
    domain: {
        type: String,
        required: true
    },
    kitId: {
        type: Number,
        required: true
    },
    sent: {
        type: Boolean,
        default: false
    },
    accessed: {
        type: Boolean,
        default: false
    },
    solved: {
        type: Boolean,
        default: false
    },
    sentAt: Date,
    accessedAt: Date,
    solvedAt: Date
}, {
    timestamps: true
});

module.exports = mongoose.model('Honeypot', HoneypotSchema);
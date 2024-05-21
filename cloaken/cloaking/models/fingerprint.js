const mongoose = require('mongoose');

const FingerprintSchema = new mongoose.Schema({
    visitorId: {
        type: String,
        required: true
    },
    honeypotId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'Honeypot',
        required: true
    }
}, {
    timestamps: true
});

module.exports = mongoose.model('Fingerprint', FingerprintSchema);
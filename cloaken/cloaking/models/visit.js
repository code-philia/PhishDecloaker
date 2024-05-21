const mongoose = require('mongoose');

const VisitSchema = new mongoose.Schema({
    honeypotId: {
        type: mongoose.Schema.Types.ObjectId,
        ref: 'Honeypot',
        required: true
    }
}, {
    timestamps: true
});

module.exports = mongoose.model('Visit', VisitSchema);
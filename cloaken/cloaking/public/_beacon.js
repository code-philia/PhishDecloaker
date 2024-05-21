// Initialize fingerprinting at application startup.
const fpPromise = import('/_fingerprint.js')
  .then(FingerprintJS => FingerprintJS.load())

const beaconUrl = "/beacon"

// Get the visitor's fingerprints on load.
window.addEventListener('load', function() {
  fpPromise
    .then(fp => fp.get())
    .then(result => {
      let honeypotId = window.location.hostname.split(".")[0];
      let fingerprint = {
        visitorId: result.visitorId,
        honeypotId
      }

      navigator.sendBeacon(beaconUrl, JSON.stringify(fingerprint));
    })
});
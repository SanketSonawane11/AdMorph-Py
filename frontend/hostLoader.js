// host_loader.js — drop this script tag on host pages with data-campaign-id attribute.
// Usage on host page:
// <script src="https://.../host_loader.js" data-backend="https://your-backend.example" data-campaign-id="camp1"></script>

(function(){
  const scriptTag = document.currentScript;
  const campaignId = scriptTag.getAttribute('data-campaign-id');
  const backend = scriptTag.getAttribute('data-backend') || 'http://localhost:8000';
  if(!campaignId) { console.error("host_loader: campaign id missing"); return; }

  // create iframe
  const iframe = document.createElement('iframe');
  iframe.style.border = "0";
  iframe.style.width = "320px";
  iframe.style.height = "250px";
  iframe.style.overflow = "hidden";
  iframe.src = `${backend}/widget/${campaignId}/wrapper`;
  iframe.sandbox = "allow-scripts allow-same-origin allow-popups"; 

  document.body.appendChild(iframe);
})();

(function () {
  const scriptTag = document.currentScript;
  const campaignId = scriptTag.getAttribute("data-campaign-id");
  const backend =
    scriptTag.getAttribute("data-backend") || "http://localhost:8000";
  
  if (!campaignId) {
    console.error("host_loader: campaign id missing");
    return;
  }

  // Create iframe 
  const iframe = document.createElement("iframe");
  iframe.style.border = "0";
  iframe.style.width = "100%";
  iframe.style.height = "100%";
  iframe.style.overflow = "hidden";
  iframe.style.borderRadius = "15px";
  iframe.src = `${backend}/widget/${campaignId}/wrapper?session=${Math.random().toString(36).slice(2)}`;
  iframe.sandbox = "allow-scripts allow-same-origin allow-popups";

  const container = document.getElementById("ad-widget-container");
  if (container) {
    container.innerHTML = '';
    container.appendChild(iframe);
  } else {
    console.error("Ad container not found, appending to body as fallback.");
    document.body.appendChild(iframe);
  }
})();
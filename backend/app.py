from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import joblib, os, json, time
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from supabase import create_client, Client

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
last_logged_predictions = {}

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase URL and Key must be set as environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Existing local file paths
ROOT = os.path.dirname(__file__)
MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.joblib")
META_PATH = os.path.join(MODEL_DIR, "meta.json")

def load_model_and_meta():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Run train_model.py first.")
    model = joblib.load(MODEL_PATH)
    with open(META_PATH) as f:
        meta = json.load(f)
    return model, meta

model, meta = load_model_and_meta()

# Simple label -> version mapping
label_to_version = {
    "not_interested": "v1",
    "hesitant": "v2",
    "curious": "v3",
    "ready": "v3"
}

# No need for init_db() as Supabase handles schema creation

class COEPHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        return response

app = FastAPI()
app.add_middleware(COEPHeaderMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

class PredictRequest(BaseModel):
    campaign_id: str
    session_id: str
    features: Dict[str, float]

@app.post("/predict")
async def predict(req: PredictRequest):
    # ... (your existing prediction logic remains unchanged)
    f_order = meta["feature_order"]
    feat_vector = []
    try:
        for k in f_order:
            feat_vector.append(float(req.features.get(k, 0.0)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad features: {e}")

    pred_int = int(model.predict([feat_vector])[0])
    label = meta["int_to_label"].get(str(pred_int))
    if not label:
        raise HTTPException(status_code=500, detail=f"Unknown label for prediction {pred_int}")

    version = label_to_version.get(label, "v2")

    # Get the last logged version from our in-memory cache
    last_version = last_logged_predictions.get(req.session_id)
    
    # Only log to the database if the version has changed
    if version != last_version:
        log_data = {
            "campaign_id": req.campaign_id,
            "session_id": req.session_id,
            "ts": int(time.time()*1000),
            "hover_count": int(req.features.get("hover_count", 0)),
            "hover_duration": int(req.features.get("hover_duration", 0)),
            "clicked": int(req.features.get("clicked", 0)),
            "time_on_ad": int(req.features.get("time_on_ad", 0)),
            "predicted_label": label,
            "predicted_version": version,
            "raw": req.features
        }

        # Log to Supabase
        supabase.table("logs").insert(log_data).execute()
        
        # Update our in-memory cache
        last_logged_predictions[req.session_id] = version

    return JSONResponse({
        "version": version,
        "label": label,
        "pred_int": pred_int,
        "features": req.features
    })

@app.get("/widget/{campaign_id}/wrapper", response_class=HTMLResponse)
async def widget_wrapper(campaign_id: str, session: str = None):
    # Fetch initial 'original' ad HTML directly
    response = supabase.table("campaigns").select("original_html").eq("campaign_id", campaign_id).single().execute()

    initial_html = ""
    if response.data and response.data.get("original_html"):
        initial_html = response.data.get("original_html")
    else:
        # Fallback to a placeholder if no data is found
        initial_html = f"<div style='padding:20px;border:1px solid #ddd; text-align:center;'>Original Ad - campaign {campaign_id} (No DB content)</div>"

    wrapper = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  html, body {{ margin: 0; padding: 0; }}
  #ad-container {{
    width:100%;
    height:100%;
    transition: opacity 0.8s ease; /* smooth fade transition */
  }}
</style>
</head>
<body>
  <div id="ad-container">{initial_html}</div>

  <script>
  const backendBase = "http://localhost:8000";
  const campaignId = "{campaign_id}";
  const sessionId = "{session or ''}" || (localStorage.getItem('ad_session') || (localStorage.setItem('ad_session', Math.random().toString(36).slice(2)), localStorage.getItem('ad_session')));

  let currentVersion = 'original'; // track last shown version
  let isLoading = false; // prevent multiple simultaneous loads

  async function loadVersion(version) {{
    if(version === currentVersion || isLoading) return;
    
    isLoading = true;
    
    try {{
      const res = await fetch(`${{backendBase}}/ad_content/${{campaignId}}/${{version}}`);
      const html = await res.text();
      const container = document.getElementById('ad-container');
      
      container.style.opacity = 0;
      setTimeout(()=>{{ 
          container.innerHTML = html; 
          container.style.opacity = 1;
          currentVersion = version;
      }}, 400);
    }} catch(error) {{
      console.error("Error loading version:", error);
    }} finally {{
      isLoading = false;
    }}
  }}

  // The initial load happens directly on the server, so no need for this call.
  // We'll keep the function here for subsequent morphing calls.
  // loadVersion(currentVersion);

  let hoverSegments = [], currentHoverStart = null, clickTimes = [], visibilitySegments = [], currentVisibleStart = Date.now();
  const container = document.getElementById('ad-container');
  container.addEventListener('mouseenter', ()=>{{ currentHoverStart = Date.now(); }});
  container.addEventListener('mouseleave', ()=>{{ 
      if(currentHoverStart){{ hoverSegments.push({{start: currentHoverStart, end: Date.now()}}); currentHoverStart = null; }} 
  }});
  container.addEventListener('click', ()=>{{ clickTimes.push(Date.now()); }});
  document.addEventListener('visibilitychange', ()=>{{ 
      if(document.visibilityState === 'hidden'){{ visibilitySegments.push({{start: currentVisibleStart, end: Date.now()}}); }}
      else{{ currentVisibleStart = Date.now(); }}
  }});

  function overlap(segStart, segEnd, winStart, winEnd) {{
    const s = Math.max(segStart, winStart);
    const e = Math.min(segEnd, winEnd);
    return Math.max(0, e - s);
  }}

  async function computeAndSend() {{
    const now = Date.now();
    const W = 10000;
    const winStart = now - W;

    let hoverDur=0, hoverCnt=0;
    let tmpSegments = hoverSegments.slice();
    if(currentHoverStart) tmpSegments.push({{start: currentHoverStart, end: now}});
    tmpSegments.forEach(seg=>{{ 
        const o = overlap(seg.start, seg.end, winStart, now); 
        if(o>0) hoverDur += o; 
        if(seg.start>=winStart && seg.start<=now) hoverCnt++; 
    }});

    const clicks = clickTimes.filter(t=>t>=winStart).length;
    let visSegments = visibilitySegments.slice();
    visSegments.push({{start: currentVisibleStart, end: now}});
    let t_on_ad = 0;
    visSegments.forEach(seg=>{{ t_on_ad += overlap(seg.start, seg.end, winStart, now); }});

    const features = {{
      hover_count: hoverCnt,
      hover_duration: Math.round(hoverDur/1000),
      clicked: clicks>0 ? 1 : 0,
      time_on_ad: Math.round(t_on_ad/1000)
    }};

    try {{
      const res = await fetch(`${{backendBase}}/predict`, {{
         method:'POST',
         headers:{{'Content-Type':'application/json'}},
         body: JSON.stringify({{campaign_id:campaignId, session_id:sessionId, features}})
      }});
      const data = await res.json();
      
      if(window.parent && window.parent !== window) {{
        window.parent.postMessage({{
          type: 'admorph_analytics',
          campaignId: campaignId,
          sessionId: sessionId,
          data: {{
            currentVersion: currentVersion,
            newVersion: data.version,
            features: features,
            prediction: data,
            timestamp: now
          }}
        }}, '*');
      }}
      
      if(data.version && data.version !== currentVersion) {{
        await loadVersion(data.version);
        if(window.parent && window.parent !== window) {{
          window.parent.postMessage({{
            type: 'admorph_analytics',
            campaignId: campaignId,
            sessionId: sessionId,
            data: {{
              type: 'state_change',
              oldVersion: currentVersion,
              newVersion: data.version,
              features: features,
              prediction: data,
              timestamp: now
            }}
          }}, '*');
        }}
      }}
    }} catch(err){{ 
      console.error("predict error", err); 
    }}
  }}
  setInterval(computeAndSend, 3000);
  </script>
</body>
</html>
"""
    return HTMLResponse(wrapper)

# Endpoint to serve ad HTML content stored in DB
@app.get("/ad_content/{campaign_id}/{version}", response_class=HTMLResponse)
async def ad_content(campaign_id: str, version: str):
    response = supabase.table("campaigns").select(f"original_html, v1_html, v2_html, v3_html").eq("campaign_id", campaign_id).limit(1).execute()
    
    if not response.data:
        default_html = {
            "original": f"<div style='padding:20px;border:1px solid #ddd'>Original Ad - campaign {campaign_id}</div>",
            "v1": "<div style='padding:20px;border:2px solid #f00'>v1 - not interested variant</div>",
            "v2": "<div style='padding:20px;border:2px solid #ffa500'>v2 - hesitant variant</div>",
            "v3": "<div style='padding:20px;border:2px solid #0a0'>v3 - engaged variant</div>"
        }
        return HTMLResponse(default_html.get(version, default_html["original"]))

    row = response.data[0]
    mapping = {
        "original": row.get("original_html", ""),
        "v1": row.get("v1_html", ""),
        "v2": row.get("v2_html", ""),
        "v3": row.get("v3_html", "")
    }
    return HTMLResponse(mapping.get(version, mapping["original"]))

# Endpoint to register a campaign and HTML (simple admin API)
@app.post("/admin/register_campaign")
async def register_campaign(payload: dict):
    campaign_id = payload.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id required")
    
    # Supabase will handle upsert (insert or update) behavior
    data, count = supabase.table("campaigns").upsert({
        "campaign_id": campaign_id,
        "original_html": payload.get("original_html"),
        "v1_html": payload.get("v1_html"),
        "v2_html": payload.get("v2_html"),
        "v3_html": payload.get("v3_html")
    }).execute()

    return {"ok": True}

# manual retrain trigger (Future)
# @app.post("/admin/retrain")
# async def retrain():
#     try:
#         import subprocess
#         subprocess.run(["python", "train_model.py"], cwd=ROOT, check=True)
#         global model, meta
#         model, meta = load_model_and_meta()
#         return {"ok": True, "msg": "retrained and reloaded model"}
#     except Exception as e:
#         return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
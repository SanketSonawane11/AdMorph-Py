# app.py
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
import joblib, os, json, sqlite3, uuid, time
from pydantic import BaseModel
from typing import Dict
from datetime import datetime

ROOT = os.path.dirname(__file__)
MODEL_DIR = os.path.join(ROOT, "models")
MODEL_PATH = os.path.join(MODEL_DIR, "model.joblib")
META_PATH = os.path.join(MODEL_DIR, "meta.json")
DB_PATH = os.path.join(ROOT, "db.sqlite3")

# Load model & meta
def load_model_and_meta():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("Model not found. Run train_model.py first.")
    model = joblib.load(MODEL_PATH)
    with open(META_PATH) as f:
        meta = json.load(f)
    return model, meta

model, meta = load_model_and_meta()

# Simple label -> version mapping
# v1 = not_interested, v2 = hesitant, v3 = interested/ready
label_to_version = {
    "not_interested": "v1",
    "hesitant": "v2",
    "curious": "v3",   # curious -> try more engaging variant
    "ready": "v3"
}

# setup DB
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS campaigns (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id TEXT UNIQUE,
      original_html TEXT,
      v1_html TEXT,
      v2_html TEXT,
      v3_html TEXT,
      created_at TEXT
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS logs (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      campaign_id TEXT,
      session_id TEXT,
      ts INTEGER,
      hover_count INTEGER,
      hover_duration INTEGER,
      clicked INTEGER,
      time_on_ad INTEGER,
      predicted_label TEXT,
      predicted_version TEXT,
      actual_outcome INTEGER,
      raw JSON
    )
    ''')
    conn.commit()
    conn.close()

init_db()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for MVP; tighten later
    allow_methods=["*"],
    allow_headers=["*"]
)

# Pydantic model for predict request
class PredictRequest(BaseModel):
    campaign_id: str
    session_id: str
    features: Dict[str, float]

@app.post("/predict")
async def predict(req: PredictRequest):
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

    # log the prediction
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
      INSERT INTO logs (campaign_id, session_id, ts, hover_count, hover_duration, clicked, time_on_ad, predicted_label, predicted_version, raw)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        req.campaign_id, req.session_id, int(time.time()*1000),
        int(req.features.get("hover_count", 0)),
        int(req.features.get("hover_duration", 0)),
        int(req.features.get("clicked", 0)),
        int(req.features.get("time_on_ad", 0)),
        label, version, json.dumps(req.features)
    ))
    conn.commit()
    conn.close()

    return JSONResponse({
        "version": version,
        "label": label,
        "pred_int": pred_int,
        "features": req.features
    })


# Endpoint to serve the iframe wrapper that will inject ad HTML
@app.get("/widget/{campaign_id}/wrapper", response_class=HTMLResponse)
async def widget_wrapper(campaign_id: str, session: str = None):
    # Minimal wrapper. It will load content from /ad_content/<campaign_id>/<version>
    # The wrapper includes the collection + sliding-window code
    wrapper = """
<!doctype html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body>
  <div id="ad-container" style="width:100%;height:100%;"></div>

  <script>
  const backendBase = "{'http://localhost:8000'}";
  const campaignId = "{campaign_id}";
  const sessionId = "{session or ''}" || (localStorage.getItem('ad_session') || (localStorage.setItem('ad_session', Math.random().toString(36).slice(2)), localStorage.getItem('ad_session')));
  // Helper to fetch ad version content and inject
  async function loadVersion(version) {{
    const res = await fetch(`${{backendBase}}/ad_content/${{campaignId}}/${{version}}`);
    const html = await res.text();
    const container = document.getElementById('ad-container');
    // simple fade
    container.style.opacity = 0;
    setTimeout(()=>{{ container.innerHTML = html; container.style.opacity = 1; }}, 200);
  }}

  // Initially load original
  loadVersion('original');

  // --------- collection logic (sliding window of 10s) ----------
  let hoverSegments = []; // {start, end}
  let currentHoverStart = null;
  let clickTimes = [];
  let visibilitySegments = []; // fallback for time_on_ad
  let currentVisibleStart = Date.now();

  // attach events to container (delegate)
  const container = document.getElementById('ad-container');
  container.addEventListener('mouseenter', ()=>{{ currentHoverStart = Date.now(); }});
  container.addEventListener('mouseleave', ()=>{{ if(currentHoverStart){ hoverSegments.push({start: currentHoverStart, end: Date.now()}); currentHoverStart=null; }}});
  container.addEventListener('click', ()=>{{ clickTimes.push(Date.now()); }});

  // when page becomes hidden/visible
  document.addEventListener('visibilitychange', ()=>{{
    if(document.visibilityState === 'hidden') {{
      // push current visible segment
      visibilitySegments.push({{start: currentVisibleStart, end: Date.now()}});
    }} else {{
      currentVisibleStart = Date.now();
    }}
  }});

  // compute overlap of a segment with lastWindow [now - 10000, now]
  function overlapWithWindow(segStart, segEnd, windowStart, windowEnd) {{
    const s = Math.max(segStart, windowStart);
    const e = Math.min(segEnd, windowEnd);
    return Math.max(0, e - s);
  }}

  async function computeAndSend() {{
    const now = Date.now();
    const W = 10000; // 10 seconds
    const winStart = now - W;

    // finalize ongoing hover if it's older than window start
    let hoverDur = 0;
    let hoverCnt = 0;
    // if currently hovering, add a virtual segment
    let tmpSegments = hoverSegments.slice();
    if(currentHoverStart) tmpSegments.push({start: currentHoverStart, end: now});

    tmpSegments.forEach(seg => {{
      const o = overlapWithWindow(seg.start, seg.end, winStart, now);
      if(o > 0) hoverDur += o;
      // count hover entries if start in window
      if(seg.start >= winStart && seg.start <= now) hoverCnt += 1;
    }});

    // clicks in window
    const clicks = clickTimes.filter(t => t >= winStart).length;

    // time_on_ad: use visibilitySegments + currentVisibleStart
    let visSegments = visibilitySegments.slice();
    visSegments.push({start: currentVisibleStart, end: now});
    let t_on_ad = 0;
    visSegments.forEach(seg => {{
      t_on_ad += overlapWithWindow(seg.start, seg.end, winStart, now);
    }});

    // convert ms -> seconds (whole seconds)
    const features = {{
      hover_count: hoverCnt,
      hover_duration: Math.round(hoverDur/1000),
      clicked: clicks > 0 ? 1 : 0,
      time_on_ad: Math.round(t_on_ad/1000)
    }};

    try {{
      const res = await fetch(`${{backendBase}}/predict`, {{
         method: 'POST',
         headers: {{'Content-Type': 'application/json'}},
         body: JSON.stringify({{campaign_id: campaignId, session_id: sessionId, features}})
      }});
      const data = await res.json();
      if(data.version) {{
         // if backend recommends a different version, load it
         // For simplicity, always load recommended version
         await loadVersion(data.version);
      }}
    }} catch(err) {{
      console.error("predict error", err);
    }}
  }}

  // run every 2 seconds (configurable)
  setInterval(computeAndSend, 2000);

  </script>
</body>
</html>
"""
    return HTMLResponse(wrapper)

# Endpoint to serve ad HTML content stored in DB
@app.get("/ad_content/{campaign_id}/{version}", response_class=HTMLResponse)
async def ad_content(campaign_id: str, version: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT original_html, v1_html, v2_html, v3_html FROM campaigns WHERE campaign_id = ?", (campaign_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        # default placeholder versions if campaign not found
        default_html = {
            "original": "<div style='padding:20px;border:1px solid #ddd'>Original Ad - campaign {}</div>".format(campaign_id),
            "v1": "<div style='padding:20px;border:2px solid #f00'>v1 - not interested variant</div>",
            "v2": "<div style='padding:20px;border:2px solid #ffa500'>v2 - hesitant variant</div>",
            "v3": "<div style='padding:20px;border:2px solid #0a0'>v3 - engaged variant</div>"
        }
        return HTMLResponse(default_html.get(version, default_html["original"]))
    orig, v1, v2, v3 = row
    mapping = {"original": orig or "", "v1": v1 or "", "v2": v2 or "", "v3": v3 or ""}
    return HTMLResponse(mapping.get(version, mapping["original"]))

# Endpoint to register a campaign and HTML (simple admin API)
@app.post("/admin/register_campaign")
async def register_campaign(payload: dict):
    # expects {"campaign_id": "camp123", "original_html": "...", "v1_html": "...", "v2_html": "...", "v3_html": "..."}
    campaign_id = payload.get("campaign_id")
    if not campaign_id:
        raise HTTPException(status_code=400, detail="campaign_id required")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
      INSERT OR REPLACE INTO campaigns (campaign_id, original_html, v1_html, v2_html, v3_html, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    ''', (campaign_id, payload.get("original_html"), payload.get("v1_html"), payload.get("v2_html"), payload.get("v3_html"), datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"ok": True}

# manual retrain trigger (MVP)
@app.post("/admin/retrain")
async def retrain():
    # for MVP, just call train_model.py; in prod, run safe retraining with data pipelines
    try:
        # naive approach: call train script — ensure correct cwd
        import subprocess
        subprocess.run(["python", "train_model.py"], cwd=ROOT, check=True)
        # reload model & meta
        global model, meta
        model, meta = load_model_and_meta()
        return {"ok": True, "msg": "retrained and reloaded model"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
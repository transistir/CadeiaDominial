# OCR Provider Research (2026-07-30)

Investigation triggered when Hiure reported PaddleOCR hosted registration is
impossible ("só funciona para chineses"). Luandro decided to self-host to
understand the challenges, then suggested WaveSpeed AI as a hosting option.

## The two-step AI pipeline

The PoC has **two independent AI steps**, each needing a different provider:

| Step | Model (SPEC) | Input → Output | Hosted at |
|---|---|---|---|
| 1. OCR | PaddleOCR-VL-1.6-0.9B | PDF → markdown (layout + text) | Baidu AI Studio (`aistudio.paddleocr.com`) |
| 2. Extraction | GLM-4.7-Flash | markdown → JSON (structured) | Z.AI / Workers AI |

**Key insight:** these are independently swappable. Replacing the OCR provider
does NOT require changing the extraction step, and vice versa. The `OcrProvider`
interface is a single function:

```typescript
interface OcrProvider {
  parseDocument(input: OcrInput): Promise<OcrOutput>;
  // Input:  { fileUrl: string }       // signed PDF URL
  // Output: { rawMarkdown: string, pageCount: number, ... }
}
```

## PaddleOCR hosted (aistudio.paddleocr.com) — BLOCKED

- Registration requires Baidu account → phone number → **Chinese phone only**
- No international email-only registration path that works reliably
- API base URL: `https://paddleocr.aistudio-app.com`
- API path: `/api/v2/ocr/jobs` (async job submission + polling + JSONL results)
- Auth: `Authorization: Bearer <PADDLEOCR_ACCESS_TOKEN>`
- **Verdict: unusable for non-Chinese users. Do not spend time on VPN/workarounds.**

## PaddleOCR-VL self-hosting — GPU mandatory

Source: `deploy/paddleocr_vl_docker/` in the PaddleOCR GitHub repo.

### Architecture (two containers)

```
┌─────────────────┐     ┌──────────────────────┐
│ Pipeline Server │────▶│ VLM Server            │
│   (PaddleX)     │     │  (FastDeploy / vLLM)  │
│ API REST        │     │  PaddleOCR-VL-1.6-0.9B│
└─────────────────┘     └──────────────────────┘
```

### Hard requirements

- **GPU required.** No CPU build exists. Supported accelerators:
  `nvidia-gpu`, `hygon-dcu`, `kunlunxin-xpu`, `metax-gpu`, `huawei-npu`,
  `intel-gpu`, `amd-gpu`
- **~8 GB VRAM minimum** (T4/L4 or better). Model is 0.9B params multimodal VL.
- **~2 GB model weights** to download (VL-1.6-0.9B + PP-DocLayoutV3)
- Docker + buildx required; build via `build_pipeline.sh --device-type nvidia-gpu`

### API contract mismatch (BLOCKER for the current adapter)

The self-hosted PaddleX serving API uses a **different endpoint and response
format** than the hosted `/api/v2/ocr/jobs` API that the current adapter
(`paddleocr-http.ts`) expects. Self-hosting requires writing a **new adapter**
(`paddleocr-paddlex.ts`) or configuring PaddleX to expose an OpenAI-compatible
wrapper. The existing `baseUrl` env var is not enough — the request/response
schema itself differs.

### Cost context

- GPU VPS (Hetzner, RunPod, AWS): ~$0.30–$1.00/hr spot, or ~$200–$400/mo reserved
- This server (Hermes VM): 2 vCPUs, 3.7 GB RAM, **no GPU** — cannot self-host

## WaveSpeed AI (wavespeed.ai) — ✅ HOSTS PaddleOCR-VL

**CORRECTED 2026-07-30:** Initial research concluded WaveSpeed had no OCR.
User provided the actual URL: `https://wavespeed.ai/models/wavespeed-ai/paddle-ocr`.
**Always search the model catalog directly before making negative claims.**

### Two products

1. **Media generation platform** — 1000+ models for image/video/audio generation
2. **OpenAI-compatible LLM proxy** (`https://llm.wavespeed.ai/v1`) — Claude, GPT, DeepSeek, Qwen, GLM
3. **Model inference API** — includes `wavespeed-ai/paddle-ocr` (PaddleOCR-VL)

### WaveSpeed PaddleOCR API contract

**Endpoint:** `POST https://api.wavespeed.ai/api/v3/wavespeed-ai/paddle-ocr`
**Auth:** `Authorization: Bearer $WAVESPEED_API_KEY`

**Input schema:**
| Param | Type | Default | Description |
|---|---|---|---|
| `image` (required) | string | — | Document image URL or base64 data URI |
| `output_format` | string | `markdown` | `markdown` or `json` |
| `enable_sync_mode` | boolean | `false` | Wait for result in same response |

**Submit response:**
```json
{ "code": 200, "data": { "id": "abc123", "status": "created",
  "urls": { "get": "https://api.wavespeed.ai/api/v3/predictions/abc123/result" } } }
```

**Poll:** GET `urls.get` with Bearer auth → `status`: created/processing/completed/failed
**Result:** On completed, `data.outputs` array contains the markdown text

**Cost:** $0.01 per run

### Critical difference: IMAGE, not PDF

WaveSpeed expects an **image URL** (not PDF). The current adapter sends `fileUrl`
(PDF URL) to PaddleOCR. For WaveSpeed, the adapter must either:
- (a) Convert PDF → images internally (challenging in Cloudflare Workers — no canvas/pdf.js)
- (b) Accept pre-converted image URLs from the client
- (c) Use the PoC's existing R2-stored images from `step1DownloadAndConvert` if
    that step already produces page images

### Open questions for implementation

**RESOLVED 2026-07-30 via API testing:**

1. **PDF acceptance: NO.** Tested with real API key (`wsk_live_iNuESq47RY9JKTqN_...`).
   - Upload PDF: ✅ accepted (type: "other", returns URL)
   - Submit with PDF URL in `image` field: ✅ accepted, but processing fails
   - Result: `"error": "Exception from the 'cv' worker: Image read Error"`
   - **Conclusion: `image` field requires actual images (PNG/JPG), not PDFs.**
   - The field name is misleading — it's a generic input field used across all WaveSpeed models.

2. **Multi-page: resolved.** Adapter uses concurrent processing with configurable limit (default 3).
   - 10-page PDF = 10 API calls × $0.01 = $0.10/doc
   - Concurrency limit prevents API rate limiting
   - Markdown concatenated with `\n\n---\n\n` separators

3. **Partial failure: fail entire job.** If any page fails, the adapter throws.
   - Rationale: downstream extraction needs complete markdown
   - Failed pages get `<!-- Page N: OCR failed -->` markers before throwing

4. **Solution: client-side PDF.js.** Browser converts PDF→PNG images before upload.
   - No server-side conversion needed (Workers lack canvas APIs)
   - PDF.js via CDN: `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.9.155/pdf.min.mjs`
   - Scale 2.0 for good OCR quality
   - Images sent as multipart form data alongside the PDF

## Decision matrix (updated 2026-07-30, verified)

| Option | OCR step | Extraction step | Cost | Effort | Status |
|---|---|---|---|---|---|
| Baidu hosted | PaddleOCR-VL | GLM via Workers AI | Pay-per-use | 0 (adapter exists) | ❌ Blocked (registration) |
| **WaveSpeed hosted** | **PaddleOCR-VL** | GLM via Workers AI | **$0.01/run** | **New adapter (image input)** | **✅ Viable — plan under Opus 5 review** |
| Self-host on GPU VPS | PaddleX serving | GLM via Workers AI | $200–$400/mo | New adapter + Docker ops | ⏳ Pending decision |
| Self-host PP-OCRv5 (non-VL, CPU) | PP-OCRv5 | GLM via Workers AI | This server (free) | New adapter + CPU inference | ⚠️ Lower quality on matrículas |
| Vision LLM pivot | Claude/GPT-4o vision | Same LLM | Per-token | Architecture change + spike | 💡 Explore |

## Environment facts (verified on this server)

- Docker 29.5.3 installed at `/usr/bin/docker`
- No NVIDIA GPU (`nvidia-smi` not found)
- 2 vCPUs, 3.7 GB RAM, 40 GB free disk
- PaddleOCR-VL self-hosting is **not feasible** on this machine

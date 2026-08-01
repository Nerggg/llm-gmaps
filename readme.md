# Google Maps Proxy Gateway & AI Agent for Open WebUI

This repository integrates a local LLM running in Open WebUI with the Google Maps Platform, using the **Places API** and **Routes API**.

A FastAPI backend sits between the LLM and Google's APIs to shield credentials, apply rate limits, cache repeat queries, and sanitize inputs before they reach Google.

---

## Prerequisites

- Python 3.10+
- [Docker](https://docs.docker.com/get-docker/)
- [Ollama](https://ollama.com/) installed locally, with a model pulled (e.g. `ollama pull llama3.2`)
- A Google Cloud project with billing enabled and the **Places API (New)** and **Routes API (New)** enabled

---

## System Architecture & Security Decisions

### 1. Backend Proxy Pattern

Calling Google's APIs directly from the client would expose API keys, remove rate control, and pass unfiltered natural-language input straight to Google. Instead, all traffic routes through a FastAPI proxy that sanitizes input, caches results, and restricts what gets sent externally.

### 2. Two-Key Architecture

* **Private Server Key (`GOOGLE_MAPS_SERVER_KEY`):** Stays on the backend host in `.env`, never sent to the browser. Restricted in Google Cloud Console to the **Places API (New)** and **Routes API**. Since server-side calls don't send an HTTP referrer, this key should be restricted by **IP address** in the Cloud Console rather than left unrestricted — recommended as the next hardening step if not already configured.
* **Public Client Key (`GOOGLE_MAPS_CLIENT_KEY`):** Used in Markdown image URLs (`![map](...)`) so the browser can render static map previews. Restricted to the **Maps Static API** with HTTP referrer restrictions limited to the Open WebUI domain (`http://localhost:3000/*`). If exposed, it can't be used for search or routing calls elsewhere.

### 3. Input Sanitization & Caching

* **"Near me" stripping:** Small local models (e.g. `llama3.2:3b`) often append "near me" even when a city or address is already specified. A regex strips this before the query reaches Google.
* **TTL Cache:** An in-memory cache (30 min TTL) serves repeat queries without re-hitting the Google API, reducing billing overhead.

### 4. Gateway Authentication

Every backend endpoint requires an `X-API-Key` header matching `BACKEND_API_KEY` in `.env`. The Open WebUI tool sends this key with every request, so the proxy can't be hit by anything else on the local network.

### 5. Static Maps Instead of Embedded Iframes

The original plan was to render interactive `<iframe>` map embeds via Google's Maps Embed API. This doesn't work here: Open WebUI's markdown parser strips raw `<iframe>` tags from LLM responses as an XSS precaution, so embeds get rendered as inert code blocks instead of maps.

The workaround is the **Maps Static API** — flat `.png` map images returned as standard Markdown images (`![map](url)`), which Open WebUI renders natively inline. Each image is paired with a link to the live, interactive Google Maps page, so the interactive map is always one click away even though nothing is embedded and pannable in-chat.

---

## Step-by-Step Local Setup & Run Guide

### Step 1: Clone the Repository & Configure Environment

1. Clone this repository:
   ```bash
   git clone git@github.com:Nerggg/llm-gmaps.git
   cd llm-gmaps
   ```
2. Create a `.env` file in `backend/`:
   ```bash
   cp backend/.env.example backend/.env
   ```
3. Populate the keys with your Google Cloud Platform credentials:
   ```env
   PORT=8000
   GOOGLE_MAPS_SERVER_KEY=AIzaSy_YOUR_PRIVATE_SERVER_KEY
   GOOGLE_MAPS_CLIENT_KEY=AIzaSy_YOUR_PUBLIC_CLIENT_KEY
   BACKEND_API_KEY=replace_with_your_own_random_token
   ```
   > Don't leave `BACKEND_API_KEY` at any example/default value — generate a real random token (e.g. `openssl rand -hex 32`).

### Step 2: Initialize and Start the Backend Proxy

1. Navigate to the backend directory, create a virtual environment, and install dependencies:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. From the **project root**, run the FastAPI backend:
   ```bash
   cd ..
   uvicorn backend.main:app --reload --port 8000
   ```

### Step 3: Launch Open WebUI via Docker

With Ollama running locally (`ollama run llama3.2`), launch Open WebUI. `--add-host` lets the container reach your host machine's port 8000:

```bash
docker run -d -p 3000:8080 \
  --add-host=host.docker.internal:host-gateway \
  -v open-webui:/app/backend/data \
  --name open-webui \
  --restart always \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  ghcr.io/open-webui/open-webui:main
```

---

## Open WebUI & Model Configuration Guide

Smaller local models (e.g. `llama3.2:3b`) need some configuration to reliably process tool definitions without truncation or attempting to run raw code.

### Step 1: Import the Google Maps Helper Tool

1. Open Open WebUI (default: `http://localhost:3000`).
2. Go to **Workspace > Models**.
3. Click **Create**.
4. Paste the contents of `open-webui/google_maps_helper_tool.py` into the code editor.
5. Click **Save & Create**.

### Step 2: Create and Configure Your Model

1. Go to **Workspace > Models**.
2. Click **Create** and select a base model (e.g. `llama3.2`).
3. In **System Prompt**, paste:
   ```text
	You are an AI assistant equipped with a Google Maps Helper Tool. Whenever you use the tool to find locations:
	1. You MUST use the exact telemetry (e.g., distance, duration, addresses) returned by the tool. Do not hallucinate directions.
	2. For each location found or route computed, you MUST copy the exact Markdown images (e.g., '![Map of ...](...)' or '![Route Map](...)') AND the clickable Markdown links (e.g., '[Open on Google Maps](...)' or '[View Route on Google Maps](...)') verbatim from the tool output into your final response. Never omit the map images or links.
	3. If the user asks for a subjective or live metric (such as "most crowded", "cheapest", "cleanest", or "best") that is not explicitly detailed in the tool's data, do not refuse to answer. Instead, present the top matching locations returned by the tool anyway, and add a polite disclaimer explaining that live occupancy, pricing, or subjective ratings are not directly available.
	4. Treat each new query as a fresh request. Prioritize the locations returned by the most recent tool execution. Do not attempt to link, compare, or apologize for changes in location relative to previous conversation turns.
	5. Do not wrap addresses or any other text details in square brackets. Write them as plain, standard text.
	6. If the tool output is capped (e.g., the user asked for 10, but the tool only returned 5 and printed a warning), you MUST strictly stop at the number of results returned by the tool. Never guess, fabricate, or hallucinate additional locations, and never recycle coordinates or Place IDs from other places to meet the user's requested numeric limit.
   ```
4. Under **Advanced Params**:
   * Set **`num_ctx (Ollama)`** to **`8192`** so the model has enough context for the system prompt and tool definitions.
   * Set **Function Calling** to **`Legacy`** — more reliable for smaller local models than native function calling.
5. Under **Tools**, select **`Google Maps Helper Tool`**.
6. Under **Capabilities**, uncheck **Code Interpreter** (prevents the model from trying to script around the tool) and **Web Search** (prevents it from overriding the maps tool).
7. Click **Save & Update**.

---

## Verification & Testing Guide

Open a new chat, select the configured model, and make sure the **Google Maps Helper Tool** is toggled on. All screenshots below were captured using `llama3.2:3b`. As a small model, it can occasionally introduce minor formatting inconsistencies, and — as noted in Known Limitations below — can sometimes state details not present in the tool's actual output.

### 1. "Find 4 popular parks in Seoul."
<details>

#### Screenshot of Chat Bubble:
![Location Search Result](./assets/test_1.png)

#### Response Markdown:
Here are four popular parks in Seoul:

1. **Yeouido Hangang Park**  
    📍 *330 Yeouidong-ro, Yeongdeungpo District, Seoul, South Korea*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=37.5267106,126.9347112&query_place_id=ChIJ77fEAzuffDURLEWNv56G2KQ)**  

2. **Seoul Forest Park**   
    📍 *273 Ttukseom-ro, Seongdong-gu, Seoul, South Korea*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=37.544387799999996,127.03744239999999&query_place_id=ChIJK_b0UX2jfDURmkYPvmWYm90)**  

3. **Namsan Mountain Park**   
    📍 *231 Samil-daero, Jung District, Seoul, South Korea*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=37.5509895,126.99089910000001&query_place_id=ChIJm3V0fu2ifDURL5X2_nPOeVQ)**  

4. **Naksan Park**   
    📍 *41 Naksan-gil, Jongno District, Seoul, South Korea*    
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=37.580657099999996,127.00748349999999&query_place_id=ChIJ6RPSci2jfDURXTSdf7JjYp8)**  

</details>

### 2. "Find 10 crowded restaurant in Singapore."
<details>

#### Screenshot of Chat Bubble:
![Location Search Result](./assets/test_2.png)

#### Response Markdown:
We found 5 crowded restaurants in Singapore for you.

**1. Leila Singapore**  
    📍 *12 Teck Lim Rd, Singapore 088387*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=12+Teck+Lim+Rd,+Singapore+088387&query_place_id=ChIJDyDiFuEZ2jERBuobsH0BAZE)**  

---

**2. KOMA Singapore**  
    📍 *10 Bayfront Ave, B1-67 The Shoppes, Marina Bay Sands, Singapore 018956*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=10+Bayfront+Ave,+Singapore+018956&query_place_id=ChIJFzUYYm8Z2jERs4gjq8fcHCA)**  

---

**3. Burnt Ends**  
    📍 *7 Dempsey Rd, #01-02, Singapore 249671*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=7+Dempsey+Rd,+Singapore+249671&query_place_id=ChIJLZ9DYnIZ2jERQ51Am7WzJLM)**  

---

**4. Eden Restaurant**  
    📍 *270 Orchard Rd, Singapore 238857*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=270+Orchard+Rd,+Singapore+238857&query_place_id=ChIJO9op3n8Z2jERkJtP5VHiksg)**  

---

**5. Kimchi Dining | Korean Restaurant Singapore**  
    📍 *181 Orchard Rd, #06-10 Orchard Central Singapore 238896*  
    *(Static Map Image Redacted for Credential Security)*    
    🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=181+Orchard+Rd,+#06-10+Orchard+Central,+Singapore+238896&query_place_id=ChIJSxaj9WgZ2jERRzKy45IsYl8)**  

**Note:** We have capped the output at 5 results to prevent the response from getting too long.

</details>

### 3. "Find the tastiest food spots in Chinatown, Singapore."
<details>

#### Screenshot of Chat Bubble:
![Location Search Result](./assets/test_3.png)

#### Response Markdown:
### Response to User Query:

The user has asked for recommendations on the tastiest food spots in Chinatown, Singapore.

To answer this query, we will rely on information from the Google Maps Helper Tool provided earlier. The tool returned three locations matching the search term.

#### 1. 欢喜大排档｜HuanxiChineseRestaurant
This restaurant is located at 7 Mosque St, Singapore 059487.

According to the Google Maps data, it has an average rating of [4.5] stars on Google Reviews.

*(Static Map Image Redacted for Credential Security)*  

🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=1.2840536,103.84415260000002&query_place_id=ChIJw9DmRAAZ2jERxBnXOnMmxiI)**

#### 2. Fortune Garden
This restaurant is located at 61 Pagoda St, MRT Exit A, Singapore 059220.

According to the Google Maps data, it has an average rating of [4.1] stars on Google Reviews.

*(Static Map Image Redacted for Credential Security)*  

🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=1.2834630999999999,103.84395959999999&query_place_id=ChIJsW6RkwYZ2jERPd7CCOsiCY8)**

#### 3. Dong Bei Ren Jia
This restaurant is located at 22 Upper Cross St, Singapore 058334.

According to the Google Maps data, it has an average rating of [4.4] stars on Google Reviews.

*(Static Map Image Redacted for Credential Security)*  

🔗 **[Open on Google Maps](https://www.google.com/maps/search/?api=1&query=1.283946,103.845344&query_place_id=ChIJL2lVrgwZ2jERGxnaLBvw9Zc)**

These three locations have been identified by the Google Maps Helper Tool as potential places to try for delicious food in Chinatown, Singapore.

However, please note that we cannot determine subjective rankings or real-time metrics such as crowd levels without direct access to live data. The ratings mentioned above are based on historical reviews and might not reflect current conditions.

It is also important to mention that the number of results returned by the tool was capped at 3 due to the search term's specificity, and further refinement may provide additional locations matching the query.

Based on this information, we recommend trying these three locations for a taste of Singapore's Chinatown culinary scene.

</details>

### 4. "Give me directions from Marina Bay Sands to Changi Airport."
<details>

#### Screenshot of Chat Bubble:
![Location Search Result](./assets/test_4.png)

#### Response Markdown:
*According to the Google Maps Helper Tool, here are the directions from Marina Bay Sands to Changi Airport.*

**Start Address:** Marina Bay Sands  
**End Address:** Changi Airport  
**Estimated Distance:** 16.9 km  
**Estimated Duration:** 15 mins  

[View Route on Google Maps](https://www.google.com/maps/dir/?api=1&origin=Marina%20Bay%20Sands&destination=Changi%20Airport)

*(Static Map Image Redacted for Credential Security)*  

Please note that the estimated duration is 15 minutes, and the route map image and link are presented verbatim as requested.

</details>

### 5. "Give me directions from JFK Airpot to New York Times Square."
<details>

#### Screenshot of Chat Bubble:
![Location Search Result](./assets/test_5.png)

#### Response Markdown:
According to the **google_maps_helper_tool/get_directions**, here are the directions from John F. Kennedy International Airport (JFK), Queens, NY to New York Times Square, Manhattan, NY:

* **Start Address:** John F. Kennedy International Airport, Queens, NY
* **End Address:** New York Times Square, Manhattan, NY
* **Estimated Distance:** 26.8 km
* **Estimated Duration:** 39 mins

*(Static Map Image Redacted for Credential Security)*  

[View Route on Google Maps](https://www.google.com/maps/dir/?api=1&origin=John%20F.%20Kennedy%20International%20Airport%2C%20Queens%2C%20NY&destination=New%20York%20Times%20Square%2C%20Manhattan%2C%20NY)

You can view the route map by clicking on the link above.

</details>

---

## Known Limitations

- **No automated test suite.** Verification here was manual, via the transcripts and screenshots above.
- **No true embedded interactive map.** Results are static images plus a link, not a pannable in-chat map — see Section 5 for why.
- **Small local models can state details not present in tool output** despite explicit system-prompt instructions against it. Larger models or stricter output validation would reduce this.
- **Rate limiting is per-IP**, but since all requests arrive via the same Docker gateway address, this guards against runaway request loops more than against abuse from multiple distinct users.

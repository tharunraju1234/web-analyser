from flask import Flask, request, jsonify, render_template_string

from website_analyzer import analyze_site
from ollama_client import analyze_grammar, rate_landing_page, summarize_in_own_words, analyze_pricing

app = Flask(__name__)

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Website Analyzer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #f6f7fb;
    --card: #ffffff;
    --border: #e8e9f0;
    --text: #1a1a2e;
    --muted: #6b6f85;
    --accent: #6366f1;
    --accent2: #8b5cf6;
    --good: #10b981;
    --mid: #f59e0b;
    --bad: #ef4444;
  }
  * { box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', -apple-system, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 0 0 60px 0;
  }
  .hero {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white;
    padding: 48px 24px 36px;
    text-align: center;
  }
  .hero h1 { margin: 0 0 6px; font-size: 28px; font-weight: 700; }
  .hero p { margin: 0; opacity: 0.9; font-size: 14px; }
  .search-wrap {
    max-width: 640px;
    margin: 24px auto 0;
    display: flex;
    gap: 10px;
    background: white;
    padding: 6px;
    border-radius: 12px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  }
  .search-wrap input {
    flex: 1;
    border: none;
    outline: none;
    padding: 12px 14px;
    font-size: 16px;
    border-radius: 8px;
    color: var(--text);
  }
  .search-wrap button {
    border: none;
    background: var(--accent);
    color: white;
    padding: 0 22px;
    border-radius: 8px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
  }
  .search-wrap button:disabled { background: #b7b8ff; cursor: not-allowed; }

  .container { max-width: 980px; margin: 0 auto; padding: 0 20px; }
  #status { text-align: center; color: var(--muted); margin-top: 24px; font-size: 14px; }
  #error { text-align: center; color: var(--bad); margin-top: 24px; font-weight: 600; }

  .site-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: 28px 0 20px;
  }
  .site-header img { width: 40px; height: 40px; border-radius: 8px; }
  .site-header h2 { margin: 0; font-size: 22px; }
  .site-header a { color: var(--muted); font-size: 13px; text-decoration: none; }

  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 20px; }
  .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; margin-bottom: 20px; }

  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
  }
  .card h3 {
    margin: 0 0 14px;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .gauge-card { text-align: center; }
  .gauge-wrap { position: relative; width: 140px; height: 140px; margin: 0 auto 10px; }
  .gauge-number { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 26px; font-weight: 700; }
  .gauge-label { font-size: 13px; color: var(--muted); margin-top: 4px; }

  .chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip {
    background: #f1f2fd;
    color: var(--accent);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    text-decoration: none;
  }
  .chip.muted { background: #f4f4f4; color: var(--muted); }

  .quote-card {
    background: #faf9ff;
    border-left: 3px solid var(--accent2);
    padding: 14px 16px;
    border-radius: 8px;
    margin-bottom: 10px;
    font-style: italic;
    color: #333;
    font-size: 14px;
  }

  .contact-list { list-style: none; padding: 0; margin: 0; }
  .contact-list li { padding: 6px 0; font-size: 14px; display: flex; gap: 8px; }
  .contact-list .icon { width: 20px; text-align: center; }

  .checklist { list-style: none; padding: 0; margin: 0; }
  .checklist li { padding: 5px 0; font-size: 14px; }
  .checklist li.pass::before { content: "✓ "; color: var(--good); font-weight: bold; }
  .checklist li.fail::before { content: "✗ "; color: var(--bad); font-weight: bold; }

  .strengths-weaknesses { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
  .strengths-weaknesses h4 { font-size: 12px; text-transform: uppercase; color: var(--muted); margin: 0 0 6px; }
  .strengths-weaknesses ul { margin: 0; padding-left: 18px; font-size: 13px; }

  details.tech-details { background: var(--card); border: 1px solid var(--border); border-radius: 14px; padding: 16px 20px; margin-bottom: 16px; }
  details.tech-details summary { cursor: pointer; font-weight: 600; color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.6px; }
  details.tech-details .tech-body { margin-top: 14px; }

  .plan-pill { display: inline-block; background: #eef; color: var(--accent2); padding: 4px 12px; border-radius: 16px; font-size: 12px; margin: 2px 4px 2px 0; }
</style>
</head>
<body>
  <div class="hero">
    <h1>🔍 Website Analyzer</h1>
    <p>Paste a URL - get a full human-style read on the site</p>
    <div class="search-wrap">
      <input type="text" id="urlInput" placeholder="example.com" autofocus>
      <button id="goBtn" onclick="runAnalysis()">Analyze</button>
    </div>
  </div>

  <div class="container">
    <div id="status"></div>
    <div id="error"></div>
    <div id="results"></div>
  </div>

<script>
document.getElementById('urlInput').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') runAnalysis();
});

let charts = [];

function destroyCharts() {
  charts.forEach(c => c.destroy());
  charts = [];
}

function scoreColor(score) {
  if (score === null || score === undefined) return '#c7c7c7';
  if (score >= 80) return '#10b981';
  if (score >= 50) return '#f59e0b';
  return '#ef4444';
}

function makeGauge(canvasId, score, max) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const value = score === null || score === undefined ? 0 : score;
  const color = scoreColor(max === 10 ? value * 10 : value);
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [value, max - value],
        backgroundColor: [color, '#eeeef5'],
        borderWidth: 0,
      }]
    },
    options: {
      cutout: '75%',
      rotation: -90,
      circumference: 180,
      plugins: { tooltip: { enabled: false }, legend: { display: false } },
      animation: { duration: 600 },
    }
  });
  charts.push(chart);
}

async function runAnalysis() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) return;

  const btn = document.getElementById('goBtn');
  const status = document.getElementById('status');
  const error = document.getElementById('error');
  const results = document.getElementById('results');

  btn.disabled = true;
  status.textContent = 'Crawling the site and running analysis - this can take 30-60 seconds for multiple pages...';
  error.textContent = '';
  results.innerHTML = '';
  destroyCharts();

  try {
    const resp = await fetch('/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url})
    });
    const data = await resp.json();

    if (!resp.ok) {
      error.textContent = data.error || 'Something went wrong.';
      status.textContent = '';
      btn.disabled = false;
      return;
    }

    status.textContent = '';
    results.innerHTML = renderResults(data);

    makeGauge('gaugeSeo', data.seo.score, 100);
    makeGauge('gaugeGrammar', data.grammar.score, 100);
    makeGauge('gaugeLanding', data.landing_rating.rating ? data.landing_rating.rating * 10 : null, 100);

  } catch (e) {
    error.textContent = 'Request failed: ' + e.message;
    status.textContent = '';
  } finally {
    btn.disabled = false;
  }
}

function esc(s) {
  if (s === null || s === undefined) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function renderResults(data) {
  const info = data.company_info;
  const seo = data.seo;
  const grammar = data.grammar;
  const landing = data.landing_rating;

  // Pages found chips
  const pages = [{label: 'Home', url: data.url}, ...data.discovered_pages];
  const pagesHtml = pages.map(p => `<a class="chip" href="${p.url}" target="_blank">${esc(p.label)}</a>`).join('');

  // About
  const aboutHtml = data.about_summary
    ? `<div class="card"><h3>📖 About - In Plain Words</h3><p>${esc(data.about_summary)}</p></div>`
    : '';

  // Testimonials
  let testimonialsHtml = '';
  if (data.testimonials && data.testimonials.length) {
    testimonialsHtml = `<div class="card"><h3>💬 Testimonials &amp; Reviews</h3>` +
      data.testimonials.map(t => `<div class="quote-card">"${esc(t.quote)}"</div>`).join('') +
      `</div>`;
  }

  // Pricing
  let pricingHtml = '';
  if (data.pricing_analysis) {
    const plans = data.pricing_analysis.plans_detected || [];
    const plansHtml = plans.length
      ? plans.map(p => `<span class="plan-pill">${esc(p)}</span>`).join('')
      : '<em>No specific plan names detected</em>';
    pricingHtml = `<div class="card"><h3>💰 Pricing Analysis</h3>
      <div style="margin-bottom:10px;">${plansHtml}</div>
      <p>${esc(data.pricing_analysis.assessment)}</p></div>`;
  }

  // Contact
  const contact = data.contact_info || {emails: [], phones: []};
  const social = data.social_handles || {};
  const socialItems = Object.keys(social).map(k =>
    `<li><span class="icon">🔗</span> <a href="${social[k]}" target="_blank">${esc(k)}: ${esc(social[k])}</a></li>`
  ).join('');
  const contactHtml = `<div class="card"><h3>📇 Contact Info</h3>
    <ul class="contact-list">
      ${contact.emails.map(e => `<li><span class="icon">✉️</span> ${esc(e)}</li>`).join('') || ''}
      ${contact.phones.map(p => `<li><span class="icon">📞</span> ${esc(p)}</li>`).join('') || ''}
      ${socialItems}
      ${(!contact.emails.length && !contact.phones.length && !socialItems) ? '<li><em>None found</em></li>' : ''}
    </ul>
  </div>`;

  // SEO checklist
  const checklistHtml = Object.entries(seo.checks).map(([key, passed]) => {
    const label = key.replace(/_/g, ' ');
    return `<li class="${passed ? 'pass' : 'fail'}">${label}</li>`;
  }).join('');

  // Landing strengths/weaknesses
  const strengths = landing.strengths || [];
  const weaknesses = landing.weaknesses || [];
  const swHtml = (strengths.length || weaknesses.length) ? `
    <div class="strengths-weaknesses">
      <div><h4>Strengths</h4><ul>${strengths.map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>
      <div><h4>Weaknesses</h4><ul>${weaknesses.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>
    </div>` : '';

  // Technical details (collapsed)
  const meta = data.meta_tags || {};
  const metaKeys = Object.keys(meta).filter(k => !k.startsWith('_') && meta[k]);
  const metaHtml = metaKeys.length
    ? '<ul>' + metaKeys.map(k => `<li><strong>${esc(k)}:</strong> ${esc(meta[k])}</li>`).join('') + '</ul>'
    : '<em>None found</em>';

  const structured = data.structured_data || [];
  const structuredHtml = structured.length
    ? `<pre style="white-space:pre-wrap;font-size:12px;background:#f5f5f5;padding:10px;border-radius:6px;">${esc(JSON.stringify(structured, null, 2))}</pre>`
    : '<em>None found</em>';

  const headings = data.headings || [];
  const headingsHtml = headings.length
    ? '<ul>' + headings.map(h => `<li>${'&nbsp;&nbsp;'.repeat(h.level - 1)}<strong>H${h.level}:</strong> ${esc(h.text)}</li>`).join('') + '</ul>'
    : '<em>None found</em>';

  const images = data.images_info || {total: 0, with_alt: 0, without_alt: 0};
  const links = data.links_info || {internal: 0, external: 0, total: 0};
  const tech = data.technology || [];

  return `
    <div class="site-header">
      ${data.favicon ? `<img src="${data.favicon}">` : ''}
      <div>
        <h2>${esc(info.name) || 'Unknown site'}</h2>
        <a href="${data.url}" target="_blank">${data.url}</a>
      </div>
    </div>

    <div class="card" style="margin-bottom:16px;">
      <h3>📄 Pages Found (${pages.length})</h3>
      <div class="chip-row">${pagesHtml}</div>
    </div>

    <div class="grid">
      <div class="card gauge-card">
        <h3>Landing Page Rating</h3>
        <div class="gauge-wrap"><canvas id="gaugeLanding"></canvas>
          <div class="gauge-number">${landing.rating !== null && landing.rating !== undefined ? landing.rating + '/10' : 'N/A'}</div>
        </div>
        <p style="font-size:13px;color:var(--muted);">${esc(landing.summary)}</p>
        ${swHtml}
      </div>

      <div class="card gauge-card">
        <h3>SEO Score</h3>
        <div class="gauge-wrap"><canvas id="gaugeSeo"></canvas>
          <div class="gauge-number">${seo.score}</div>
        </div>
        <ul class="checklist" style="text-align:left;">${checklistHtml}</ul>
      </div>

      <div class="card gauge-card">
        <h3>Grammar &amp; Writing</h3>
        <div class="gauge-wrap"><canvas id="gaugeGrammar"></canvas>
          <div class="gauge-number">${grammar.score !== null ? grammar.score : 'N/A'}</div>
        </div>
        <p style="font-size:13px;color:var(--muted);">${esc(grammar.summary)}</p>
      </div>
    </div>

    <div class="grid-2">
      ${aboutHtml}
      ${pricingHtml}
    </div>

    <div class="grid-2">
      ${testimonialsHtml}
      ${contactHtml}
    </div>

    <details class="tech-details">
      <summary>⚙️ Technical Details (meta tags, structured data, images, links, tech stack)</summary>
      <div class="tech-body">
        <p><strong>Word count:</strong> ${data.word_count} &nbsp;|&nbsp; <strong>Images:</strong> ${images.total} (${images.with_alt} with alt text) &nbsp;|&nbsp; <strong>Links:</strong> ${links.total} (${links.internal} internal / ${links.external} external)</p>
        <p><strong>Technology detected:</strong> ${tech.length ? esc(tech.join(', ')) : '<em>Nothing detected</em>'}</p>
        <p><strong>Heading outline:</strong></p>
        ${headingsHtml}
        <p><strong>Meta tags:</strong></p>
        ${metaHtml}
        <p><strong>Structured data (JSON-LD):</strong></p>
        ${structuredHtml}
      </div>
    </details>
  `;
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/analyze", methods=["POST"])
def analyze_route():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        result = analyze_site(url)
    except Exception as e:
        return jsonify({"error": f"Failed to load or parse the site: {e}"}), 500

    try:
        grammar_result = analyze_grammar(result["home_visible_text"])
    except Exception as e:
        grammar_result = {"score": None, "issue_count": 0, "examples": [], "summary": f"Grammar check failed: {e}"}

    try:
        landing_rating = rate_landing_page(result["home_visible_text"])
    except Exception as e:
        landing_rating = {"rating": None, "strengths": [], "weaknesses": [], "summary": f"Rating failed: {e}"}

    about_entry = result["sub_pages"].get("about")
    about_summary = None
    if about_entry and about_entry.get("visible_text"):
        try:
            about_summary = summarize_in_own_words(about_entry["visible_text"], context="the About page")
        except Exception:
            about_summary = None

    pricing_entry = result["sub_pages"].get("pricing")
    pricing_analysis = None
    if pricing_entry and pricing_entry.get("visible_text"):
        try:
            pricing_analysis = analyze_pricing(pricing_entry["visible_text"])
        except Exception:
            pricing_analysis = None

    testimonials = list(result["home_testimonials"])
    testimonials_page = result["sub_pages"].get("testimonials")
    if testimonials_page and testimonials_page.get("testimonials_heuristic"):
        testimonials += testimonials_page["testimonials_heuristic"]
    testimonials = testimonials[:8]

    contact_entry = result["sub_pages"].get("contact")
    if contact_entry and contact_entry.get("contact_info"):
        contact_info = contact_entry["contact_info"]
        social_handles = contact_entry.get("social_handles") or result["company_info"]["social_handles"]
    else:
        contact_info = result["home_contact_info"]
        social_handles = result["company_info"]["social_handles"]

    return jsonify({
        "url": result["url"],
        "status": result["status"],
        "favicon": result["favicon"],
        "word_count": result["word_count"],
        "company_info": result["company_info"],
        "seo": result["seo"],
        "grammar": grammar_result,
        "landing_rating": landing_rating,
        "discovered_pages": result["discovered_pages"],
        "about_summary": about_summary,
        "pricing_analysis": pricing_analysis,
        "testimonials": testimonials,
        "contact_info": contact_info,
        "social_handles": social_handles,
        "meta_tags": result["meta_tags"],
        "structured_data": result["structured_data"],
        "headings": result["headings"],
        "images_info": result["images_info"],
        "links_info": result["links_info"],
        "technology": result["technology"],
    })


if __name__ == "__main__":
    print("Starting Website Analyzer at http://localhost:5000")
    app.run(debug=True, port=5000)
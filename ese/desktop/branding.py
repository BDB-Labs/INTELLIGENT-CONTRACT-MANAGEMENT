from __future__ import annotations

from ese.desktop.config import DesktopSurfaceSpec


def render_splash_html(surface: DesktopSurfaceSpec) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{surface.headline}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg-0: #04101d;
      --bg-1: #0c1b2b;
      --panel: rgba(12, 24, 39, 0.86);
      --line: rgba(255, 255, 255, 0.10);
      --ink: #f5f7fb;
      --muted: rgba(230, 238, 247, 0.72);
      --accent-a: {surface.accent_start};
      --accent-b: {surface.accent_end};
      --glow: {surface.glow};
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 12% 12%, rgba(120,255,214,0.18), transparent 24%),
        radial-gradient(circle at 88% 18%, rgba(0,124,240,0.22), transparent 28%),
        linear-gradient(160deg, var(--bg-0), var(--bg-1) 52%, #09111b);
      overflow: hidden;
    }}

    .noise {{
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: radial-gradient(circle at center, black 42%, transparent 88%);
      opacity: 0.45;
      pointer-events: none;
    }}

    main {{
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(300px, 0.9fr);
      gap: 28px;
      align-items: center;
      min-height: 100vh;
      padding: 40px;
    }}

    .hero {{
      position: relative;
      z-index: 1;
    }}

    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.04);
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.76rem;
      font-weight: 700;
      color: var(--muted);
    }}

    .eyebrow::before {{
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--accent-a), var(--accent-b));
      box-shadow: 0 0 18px var(--glow);
    }}

    h1 {{
      margin: 18px 0 10px;
      font-size: clamp(3rem, 7vw, 5.8rem);
      line-height: 0.92;
      letter-spacing: -0.06em;
      max-width: 10ch;
    }}

    h1 span {{
      display: block;
      background: linear-gradient(135deg, #ffffff, var(--accent-a) 36%, var(--accent-b) 88%);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}

    .lead {{
      max-width: 62ch;
      font-size: 1.08rem;
      line-height: 1.7;
      color: var(--muted);
      margin-top: 18px;
    }}

    .pulse {{
      position: absolute;
      right: -120px;
      top: 50%;
      width: 360px;
      height: 360px;
      transform: translateY(-50%);
      border-radius: 999px;
      background:
        radial-gradient(circle, rgba(120,255,214,0.42) 0%, rgba(120,255,214,0.08) 28%, transparent 58%),
        radial-gradient(circle, rgba(0,124,240,0.38) 0%, transparent 62%);
      filter: blur(8px);
      animation: breathe 4.6s ease-in-out infinite;
      opacity: 0.9;
    }}

    .panel {{
      position: relative;
      z-index: 1;
      padding: 26px;
      border-radius: 28px;
      border: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)),
        var(--panel);
      box-shadow:
        0 0 0 1px rgba(255,255,255,0.03) inset,
        0 24px 80px rgba(0,0,0,0.32);
      backdrop-filter: blur(16px);
    }}

    .panel h2 {{
      margin: 0;
      font-size: 1.08rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
    }}

    .panel p {{
      margin: 16px 0 0;
      color: var(--ink);
      font-size: 1rem;
      line-height: 1.65;
    }}

    .status {{
      display: grid;
      gap: 12px;
      margin-top: 20px;
    }}

    .row {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.08);
      background: rgba(255,255,255,0.03);
      font-size: 0.95rem;
    }}

    .row strong {{
      font-weight: 700;
      color: var(--ink);
    }}

    .boot {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--accent-a);
      font-weight: 700;
    }}

    .boot::before {{
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(135deg, var(--accent-a), var(--accent-b));
      box-shadow: 0 0 14px var(--glow);
      animation: blink 1.3s ease-in-out infinite;
    }}

    @keyframes blink {{
      0%, 100% {{ opacity: 0.35; transform: scale(0.9); }}
      50% {{ opacity: 1; transform: scale(1.05); }}
    }}

    @keyframes breathe {{
      0%, 100% {{ transform: translateY(-50%) scale(0.96); opacity: 0.74; }}
      50% {{ transform: translateY(-50%) scale(1.06); opacity: 1; }}
    }}

    @media (max-width: 980px) {{
      main {{
        grid-template-columns: 1fr;
      }}

      .pulse {{
        top: auto;
        bottom: -140px;
        right: 50%;
        transform: translateX(50%);
      }}
    }}
  </style>
</head>
<body>
  <div class="noise"></div>
  <main>
    <section class="hero">
      <div class="pulse"></div>
      <div class="eyebrow">{surface.subtitle}</div>
      <h1><span>{surface.headline}</span></h1>
      <p class="lead">{surface.supporting_copy}</p>
    </section>
    <aside class="panel">
      <h2>{surface.title}</h2>
      <p>
        Spinning up the local runtime, binding a private loopback surface, and
        preparing the desktop shell. This architecture is intentionally extensible:
        the same shell can host future Windows and SaaS-adjacent surfaces without
        reworking the runtime contract.
      </p>
      <div class="status">
        <div class="row"><span>Surface</span><strong>{surface.key}</strong></div>
        <div class="row"><span>Shell</span><strong>Native webview</strong></div>
        <div class="row"><span>Platform posture</span><strong>macOS-first, multi-platform-ready</strong></div>
        <div class="row"><span>Runtime status</span><strong class="boot">Booting local services</strong></div>
      </div>
    </aside>
  </main>
</body>
</html>
"""

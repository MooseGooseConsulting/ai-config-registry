#!/usr/bin/env python3
"""Generate a self-contained HTML dashboard from a registry snapshot."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

from registry_scan_lib import redact_sensitive_text


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "working" / "registry_snapshot.json"
OUTPUT_PATH = ROOT / "working" / "registry-dashboard.html"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        tags = [str(item).strip() for item in value if str(item).strip()]
        return tags
    if isinstance(value, str):
        if "," in value:
            return [part.strip() for part in value.split(",") if part.strip()]
        value = value.strip()
        return [value] if value else []
    return []


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unnamed"


def _read_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Snapshot not found: {path}. Create working/registry_snapshot.json first."
        )
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Snapshot file must contain a JSON object at the top level.")
    return data


def _resolve_timestamp(snapshot: dict[str, Any]) -> str:
    candidates = (
        snapshot.get("snapshot_timestamp"),
        snapshot.get("generated_at"),
        snapshot.get("timestamp"),
        snapshot.get("metadata", {}).get("timestamp")
        if isinstance(snapshot.get("metadata"), dict)
        else None,
    )
    for value in candidates:
        if value:
            return _as_text(value)
    return datetime.now(timezone.utc).isoformat()


def _ecosystem_name_map(snapshot: dict[str, Any]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for eco in _as_list(snapshot.get("ecosystems")):
        if isinstance(eco, dict) and "id" in eco and "name" in eco:
            mapping[int(eco["id"])] = _as_text(eco["name"])
    local_map = snapshot.get("ecosystem_name_by_local_id")
    if isinstance(local_map, dict):
        for key, value in local_map.items():
            mapping[int(key)] = _as_text(value)
    return mapping


def _normalize_skills(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    eco_map = _ecosystem_name_map(snapshot)
    rows: list[dict[str, Any]] = []
    for skill in _as_list(snapshot.get("skills")):
        if not isinstance(skill, dict):
            continue
        eco_ids = skill.get("ecosystem_ids", [])
        eco_names = [eco_map.get(int(eid), "") for eid in eco_ids if eid is not None]
        name = _as_text(skill.get("name"), "Unnamed")
        rows.append(
            {
                "name": name,
                "slug": _slugify(name),
                "ecosystem": ", ".join(name for name in eco_names if name),
                "source_of_truth": skill.get("source_of_truth", ""),
                "version": "",
                "tags": _normalize_tags(skill.get("tags")),
                "source_path": _as_text(skill.get("path")),
            }
        )
    return rows


def _normalize_hooks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    eco_map = _ecosystem_name_map(snapshot)
    rows: list[dict[str, Any]] = []
    for hook in _as_list(snapshot.get("hooks")):
        if not isinstance(hook, dict):
            continue
        eco_id = hook.get("ecosystem_id")
        rows.append(
            {
                "hook_name": Path(_as_text(hook.get("path"))).name,
                "event_name": _as_text(hook.get("event_type")),
                "command": _as_text(hook.get("action")),
                "ecosystem": eco_map.get(int(eco_id), "") if eco_id is not None else "",
                "is_enabled": "",
            }
        )
    return rows


def _normalize_cli_tools(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for tool in _as_list(snapshot.get("cli_tools")):
        if not isinstance(tool, dict):
            continue
        rows.append(
            {
                "tool_name": _as_text(tool.get("name")),
                "min_version": _as_text(tool.get("version")),
                "is_required": "",
                "install_hint": _as_text(tool.get("path")),
                "ecosystem": "available" if tool.get("available") else "missing",
            }
        )
    return rows


def _normalize_secrets(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in _as_list(snapshot.get("secrets_manifest")):
        if not isinstance(entry, dict):
            continue
        rows.append(
            {
                "secret_key": _as_text(entry.get("secret_name") or entry.get("secret_key")),
                "provider": "doppler",
                "project": _as_text(entry.get("doppler_project")),
                "config": _as_text(entry.get("doppler_config")),
                "required": "",
                "description": f"{len(_as_list(entry.get('locations')))} location(s)",
                "ecosystem": "",
            }
        )
    return rows


def _normalize_mcp_servers(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for server in _as_list(snapshot.get("mcp_servers")):
        if not isinstance(server, dict):
            continue
        sources = server.get("ecosystem_sources") or server.get("metadata", {}).get("sources", [])
        if not isinstance(sources, list):
            sources = []
        for source in sources:
            rows.append(
                {
                    "display_name": _as_text(server.get("name")),
                    "slug": _slugify(_as_text(server.get("name"))),
                    "ecosystem": _as_text(source),
                    "command_or_url": redact_sensitive_text(_as_text(server.get("command_or_url"))),
                    "has_plaintext_secret": server.get("has_plaintext_secret", False),
                }
            )
        if not sources:
            rows.append(
                {
                    "display_name": _as_text(server.get("name")),
                    "slug": _slugify(_as_text(server.get("name"))),
                    "ecosystem": "",
                    "command_or_url": redact_sensitive_text(_as_text(server.get("command_or_url"))),
                    "has_plaintext_secret": server.get("has_plaintext_secret", False),
                }
            )
    return rows


def _row_cells(row: dict[str, Any], columns: list[tuple[str, str]]) -> str:
    cells: list[str] = []
    for key, fallback in columns:
        value = row.get(key, fallback)
        if isinstance(value, (dict, list)):
            rendered = escape(json.dumps(value, ensure_ascii=False))
        else:
            rendered = escape(_as_text(value, fallback))
        cells.append(f"<td>{rendered}</td>")
    return "".join(cells)


def _render_table(title: str, rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    header = "".join(f"<th>{escape(label)}</th>" for label, _ in columns)
    if rows:
        body = "".join(f"<tr>{_row_cells(row, columns)}</tr>" for row in rows)
    else:
        body = (
            f"<tr><td colspan='{len(columns)}' class='empty'>No {escape(title.lower())} entries</td></tr>"
        )
    return (
        "<div class='table-wrap'>"
        f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
        "</div>"
    )


def _build_mcp_matrix(mcp_rows: list[dict[str, Any]], ecosystems: list[dict[str, Any]]) -> tuple[str, list[str]]:
    ecosystem_labels: list[str] = []
    seen_ecosystems: set[str] = set()
    for item in ecosystems:
        name = _as_text(item.get("name"), "").strip()
        if name and name not in seen_ecosystems:
            seen_ecosystems.add(name)
            ecosystem_labels.append(name)

    presence: dict[str, dict[str, bool]] = {}
    for row in mcp_rows:
        server = _as_text(row.get("display_name") or row.get("slug"), "Unknown Server")
        eco = _as_text(row.get("ecosystem"), "").strip()
        if server not in presence:
            presence[server] = {}
        if eco:
            if eco not in seen_ecosystems:
                seen_ecosystems.add(eco)
                ecosystem_labels.append(eco)
            presence[server][eco] = True

    if not presence:
        return (
            "<div class='table-wrap'><table><tbody>"
            "<tr><td class='empty'>No MCP servers found</td></tr>"
            "</tbody></table></div>",
            ecosystem_labels,
        )

    header = "<th>Server</th>" + "".join(f"<th>{escape(eco)}</th>" for eco in ecosystem_labels)
    rows: list[str] = []
    for server_name in sorted(presence):
        cells = [f"<td>{escape(server_name)}</td>"]
        for eco in ecosystem_labels:
            icon = "&#10003;" if presence[server_name].get(eco) else "&mdash;"
            css = "presence-yes" if presence[server_name].get(eco) else "presence-no"
            cells.append(f"<td class='{css}'>{icon}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    html = (
        "<div class='table-wrap'><table>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table></div>"
    )
    return html, ecosystem_labels


def _render_summary_cards(snapshot: dict[str, Any]) -> str:
    ecosystems = _as_list(snapshot.get("ecosystems"))
    skills = _as_list(snapshot.get("skills"))
    mcp_count = snapshot.get("mcp_server_count", len(_as_list(snapshot.get("mcp_servers"))))
    hooks = _as_list(snapshot.get("hooks"))
    cards = [
        ("Ecosystems", len(ecosystems)),
        ("Skills", len(skills)),
        ("MCP Servers", mcp_count),
        ("Hooks", len(hooks)),
    ]
    items = "".join(
        f"<div class='card'><div class='card-value'>{value}</div><div class='card-label'>{escape(label)}</div></div>"
        for label, value in cards
    )
    return f"<section class='summary-cards'>{items}</section>"


def _render_extra_surfaces(snapshot: dict[str, Any]) -> str:
    extra = snapshot.get("extra_surfaces")
    if not isinstance(extra, dict):
        return "<p class='empty'>No extra surfaces captured.</p>"
    rows: list[dict[str, str]] = []
    for surface_name, entries in extra.items():
        if surface_name == "global_runtime_inventory":
            rows.append({"surface": surface_name, "detail": "runtime inventory captured"})
            continue
        if isinstance(entries, list):
            found = len([entry for entry in entries if isinstance(entry, dict) and entry.get("exists")])
            rows.append({"surface": surface_name, "detail": f"{found}/{len(entries)} paths present"})
    return _render_table("Extra Surfaces", rows, [("surface", ""), ("detail", "")])


def _render_mcp_sources(snapshot: dict[str, Any]) -> str:
    sources = snapshot.get("mcp_sources")
    if not isinstance(sources, dict):
        return "<p class='empty'>No MCP sources captured.</p>"
    rows = [
        {
            "source": name,
            "status": _as_text(details.get("status")),
            "path": _as_text(details.get("path")),
        }
        for name, details in sorted(sources.items())
        if isinstance(details, dict)
    ]
    return _render_table("MCP Sources", rows, [("source", ""), ("status", ""), ("path", "")])


def generate_dashboard(snapshot_path: Path = SNAPSHOT_PATH, output_path: Path = OUTPUT_PATH) -> Path:
    snapshot = _read_snapshot(snapshot_path)
    timestamp = _resolve_timestamp(snapshot)

    ecosystems = _as_list(snapshot.get("ecosystems"))
    skills = _normalize_skills(snapshot)
    mcp_servers = _normalize_mcp_servers(snapshot)
    hooks = _normalize_hooks(snapshot)
    cli_tools = _normalize_cli_tools(snapshot)
    secrets_manifest = _normalize_secrets(snapshot)

    mcp_matrix_html, _ = _build_mcp_matrix(mcp_servers, ecosystems)
    summary_cards = _render_summary_cards(snapshot)
    extra_surfaces_html = _render_extra_surfaces(snapshot)
    mcp_sources_html = _render_mcp_sources(snapshot)
    mcp_detail_table = _render_table(
        "MCP Server Details",
        mcp_servers,
        [
            ("display_name", ""),
            ("ecosystem", ""),
            ("command_or_url", ""),
            ("has_plaintext_secret", ""),
        ],
    )

    payload = {
        "timestamp": timestamp,
        "skills": skills,
    }

    skills_table = _render_table(
        "Skills",
        skills,
        [
            ("name", "Unnamed"),
            ("slug", ""),
            ("ecosystem", ""),
            ("source_of_truth", ""),
            ("version", ""),
            ("tags", ""),
            ("source_path", ""),
        ],
    )
    hooks_table = _render_table(
        "Hooks",
        hooks,
        [
            ("hook_name", ""),
            ("event_name", ""),
            ("command", ""),
            ("ecosystem", ""),
            ("is_enabled", ""),
        ],
    )
    cli_table = _render_table(
        "CLI Tools",
        cli_tools,
        [
            ("tool_name", ""),
            ("min_version", ""),
            ("is_required", ""),
            ("install_hint", ""),
            ("ecosystem", ""),
        ],
    )
    secrets_table = _render_table(
        "Secrets Manifest",
        secrets_manifest,
        [
            ("secret_key", ""),
            ("provider", ""),
            ("project", ""),
            ("config", ""),
            ("required", ""),
            ("description", ""),
            ("ecosystem", ""),
        ],
    )
    ecosystems_table = _render_table(
        "Ecosystems",
        [eco for eco in ecosystems if isinstance(eco, dict)],
        [("name", ""), ("type", ""), ("config_path", "")],
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Registry Dashboard</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #111831;
      --panel-2: #151e3e;
      --text: #e7ecff;
      --muted: #9aa7d5;
      --accent: #60a5fa;
      --border: #2b3a67;
      --good: #1d4f33;
      --bad: #3f2430;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Segoe UI, Roboto, Arial, sans-serif;
      background: linear-gradient(180deg, #070b17 0%, var(--bg) 100%);
      color: var(--text);
    }}
    .container {{
      width: min(1400px, 94vw);
      margin: 24px auto 40px;
    }}
    .header {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px 18px;
      margin-bottom: 16px;
    }}
    .header h1 {{
      margin: 0 0 8px;
      font-size: 22px;
    }}
    .timestamp {{
      color: var(--muted);
      font-size: 13px;
    }}
    .summary-cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px;
      text-align: center;
    }}
    .card-value {{
      font-size: 24px;
      font-weight: 700;
    }}
    .card-label {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 14px;
    }}
    .tab-btn {{
      border: 1px solid var(--border);
      background: var(--panel-2);
      color: var(--text);
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      font-weight: 600;
    }}
    .tab-btn.active {{
      border-color: var(--accent);
      box-shadow: inset 0 0 0 1px var(--accent);
    }}
    .tab-panel {{
      display: none;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px;
    }}
    .tab-panel.active {{
      display: block;
    }}
    .controls {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }}
    label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    input, select {{
      width: 100%;
      border: 1px solid var(--border);
      background: #0c1430;
      color: var(--text);
      border-radius: 8px;
      padding: 8px 10px;
    }}
    .table-wrap {{
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 12px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 900px;
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #0f1835;
      z-index: 1;
    }}
    tbody tr:hover {{
      background: #132149;
    }}
    .empty {{
      color: var(--muted);
      text-align: center;
      padding: 24px;
    }}
    .presence-yes {{
      text-align: center;
      background: var(--good);
    }}
    .presence-no {{
      text-align: center;
      background: var(--bad);
      color: #c7bfd0;
    }}
    .hint {{
      margin: 0 0 10px;
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <section class="header">
      <h1>AI Config Registry Dashboard</h1>
      <div class="timestamp">Snapshot timestamp: <strong>{escape(timestamp)}</strong></div>
    </section>

    {summary_cards}

    <nav class="tabs" aria-label="Dashboard tabs">
      <button class="tab-btn active" data-tab="skills">Skills</button>
      <button class="tab-btn" data-tab="mcp">MCP Servers</button>
      <button class="tab-btn" data-tab="hooks">Hooks</button>
      <button class="tab-btn" data-tab="cli-tools">CLI Tools</button>
      <button class="tab-btn" data-tab="secrets">Secrets Manifest</button>
      <button class="tab-btn" data-tab="overview">Overview</button>
    </nav>

    <section id="tab-skills" class="tab-panel active">
      <p class="hint">Filter skills by ecosystem, source of truth, and tag text.</p>
      <div class="controls">
        <div>
          <label for="skills-ecosystem">Ecosystem</label>
          <select id="skills-ecosystem">
            <option value="">All ecosystems</option>
          </select>
        </div>
        <div>
          <label for="skills-source">Source Of Truth</label>
          <select id="skills-source">
            <option value="">All sources</option>
          </select>
        </div>
        <div>
          <label for="skills-tag-query">Tag Text Search</label>
          <input id="skills-tag-query" type="text" placeholder="e.g. supabase, mcp, ui" />
        </div>
      </div>
      <div id="skills-table-container">{skills_table}</div>
    </section>

    <section id="tab-mcp" class="tab-panel">
      <p class="hint">Matrix view of MCP server presence across ecosystems.</p>
      {mcp_matrix_html}
      {mcp_detail_table}
      {mcp_sources_html}
    </section>

    <section id="tab-hooks" class="tab-panel">
      {hooks_table}
    </section>

    <section id="tab-cli-tools" class="tab-panel">
      {cli_table}
    </section>

    <section id="tab-secrets" class="tab-panel">
      {secrets_table}
    </section>

    <section id="tab-overview" class="tab-panel">
      <p class="hint">Ecosystem summary and additional enumeration surfaces.</p>
      {ecosystems_table}
      {extra_surfaces_html}
    </section>
  </div>

  <script>
    (function() {{
      const snapshot = {json.dumps(payload, ensure_ascii=False)};
      const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
      const tabPanels = Array.from(document.querySelectorAll(".tab-panel"));
      const ecosystemSelect = document.getElementById("skills-ecosystem");
      const sourceSelect = document.getElementById("skills-source");
      const tagQueryInput = document.getElementById("skills-tag-query");
      const tableContainer = document.getElementById("skills-table-container");

      function escapeHtml(value) {{
        const div = document.createElement("div");
        div.textContent = String(value ?? "");
        return div.innerHTML;
      }}

      function renderSkillsTable(rows) {{
        if (!rows.length) {{
          tableContainer.innerHTML =
            "<div class='table-wrap'><table><tbody><tr><td class='empty'>No skills match current filters</td></tr></tbody></table></div>";
          return;
        }}

        const body = rows.map((row) => {{
          const tags = Array.isArray(row.tags) ? row.tags.join(", ") : "";
          return `
            <tr>
              <td>${{escapeHtml(row.name || "Unnamed")}}</td>
              <td>${{escapeHtml(row.slug || "")}}</td>
              <td>${{escapeHtml(row.ecosystem || "")}}</td>
              <td>${{escapeHtml(row.source_of_truth || "")}}</td>
              <td>${{escapeHtml(row.version || "")}}</td>
              <td>${{escapeHtml(tags)}}</td>
              <td>${{escapeHtml(row.source_path || "")}}</td>
            </tr>`;
        }}).join("");

        tableContainer.innerHTML = `
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Slug</th>
                  <th>Ecosystem</th>
                  <th>Source Of Truth</th>
                  <th>Version</th>
                  <th>Tags</th>
                  <th>Source Path</th>
                </tr>
              </thead>
              <tbody>${{body}}</tbody>
            </table>
          </div>`;
      }}

      function uniqueSorted(values) {{
        return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
      }}

      function hydrateFilters() {{
        const ecosystems = uniqueSorted(snapshot.skills.map((skill) => skill.ecosystem || ""));
        const sources = uniqueSorted(snapshot.skills.map((skill) => skill.source_of_truth || ""));
        ecosystems.forEach((value) => {{
          const option = document.createElement("option");
          option.value = value;
          option.textContent = value;
          ecosystemSelect.appendChild(option);
        }});
        sources.forEach((value) => {{
          const option = document.createElement("option");
          option.value = value;
          option.textContent = value;
          sourceSelect.appendChild(option);
        }});
      }}

      function applySkillsFilters() {{
        const ecosystem = ecosystemSelect.value.trim().toLowerCase();
        const source = sourceSelect.value.trim().toLowerCase();
        const query = tagQueryInput.value.trim().toLowerCase();

        const filtered = snapshot.skills.filter((skill) => {{
          const skillEcosystem = String(skill.ecosystem || "").toLowerCase();
          const skillSource = String(skill.source_of_truth || "").toLowerCase();
          const tags = Array.isArray(skill.tags) ? skill.tags.map((tag) => String(tag).toLowerCase()) : [];
          if (ecosystem && !skillEcosystem.includes(ecosystem)) {{
            return false;
          }}
          if (source && skillSource !== source) {{
            return false;
          }}
          if (query && !tags.some((tag) => tag.includes(query))) {{
            return false;
          }}
          return true;
        }});

        renderSkillsTable(filtered);
      }}

      function activateTab(tabName) {{
        tabButtons.forEach((button) => {{
          button.classList.toggle("active", button.dataset.tab === tabName);
        }});
        tabPanels.forEach((panel) => {{
          panel.classList.toggle("active", panel.id === `tab-${{tabName}}`);
        }});
      }}

      tabButtons.forEach((button) => {{
        button.addEventListener("click", () => activateTab(button.dataset.tab));
      }});
      ecosystemSelect.addEventListener("change", applySkillsFilters);
      sourceSelect.addEventListener("change", applySkillsFilters);
      tagQueryInput.addEventListener("input", applySkillsFilters);

      hydrateFilters();
      applySkillsFilters();
      activateTab("skills");
    }})();
  </script>
</body>
</html>
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    output_path = generate_dashboard()
    print(f"Dashboard generated: {output_path}")


if __name__ == "__main__":
    main()

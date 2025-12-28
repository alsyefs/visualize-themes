# backend/report_template.py


def get_dynamic_faq(config):
    """
    Generates FAQ items based on the provided configuration object.
    """
    faq_items = []

    # Get configuration values securely using getattr
    overlap_pct = getattr(config, "WORDS_OVERLAP_PERCENTAGE", 0.0) * 100
    align_segments = getattr(config, "ALIGN_SEGMENTS_ACROSS_CODES", False)
    margin_pct = getattr(config, "TRANSCRIPT_NON_CODABLE_MARGIN", 0.10) * 100
    strijbos_method = getattr(config, "STRIJBOS_METHOD", "METHOD_C")

    # ==============================================================================
    # SECTION 1: DATA PROCESSING & MERGING
    # ==============================================================================

    # Add Dynamic Method Explanation
    method_title = f"Current Method: {strijbos_method}"
    method_desc = ""

    if strijbos_method == "METHOD_A":
        method_desc = (
            "We are using <strong>Strijbos Method A (Intersection)</strong>.<br>"
            "This calculates agreement <em>only</em> on text segments that were coded by <strong>ALL</strong> coders. "
            "Segments where one coder marked something and another did not (Omissions) are excluded from the statistics."
        )
    elif strijbos_method == "METHOD_B":
        method_desc = (
            "We are using <strong>Strijbos Method B (Union)</strong>.<br>"
            "This includes any segment marked by <strong>at least one</strong> coder. "
            "It treats Omissions (Coder A says 'Code X', Coder B says nothing) as Disagreements (1 vs 0)."
        )
    else:  # METHOD_C
        method_desc = (
            "We are using <strong>Strijbos Method C (Full Universe)</strong>.<br>"
            "This includes all coded segments AND estimated 'True Negatives' (silence) from the transcripts. "
            "It provides the most complete picture of agreement over the entire duration of the text."
        )

    faq_items.append(
        {
            "q": "Which statistical method is being used in this report?",
            "a": f"{method_desc}",
        }
    )

    faq_items.append(
        {
            "q": "Why do some of my text selections look different or longer than what I originally coded?",
            "a": (
                f"This is due to the <strong>Fuzzy Matching & Merging</strong> process.<br><br>"
                f"<strong>The Logic:</strong> The system compares text segments from different coders. If two segments share "
                f"at least <strong>{overlap_pct:.0f}%</strong> of their unique words (tokens), they are considered to be the 'same' segment.<br>"
                f"<strong>The Result:</strong> To preserve the full context of what both coders saw, the system merges them by keeping "
                f"the <strong>longest version</strong> of the text."
            ),
        }
    )

    faq_items.append(
        {
            "q": "What do the colors in the 'Browser' tab indicate?",
            "a": (
                "<ul>"
                "<li><strong style='color: var(--success)'>Green Text (80%+ Agreement):</strong> High consensus.</li>"
                "<li><strong style='color: #fd7e14'>Orange Text (60-80%):</strong> Moderate agreement.</li>"
                "<li><strong style='color: var(--primary)'>Blue Text (<60%):</strong> Low agreement.</li>"
                "</ul>"
            ),
        }
    )

    # ==============================================================================
    # SECTION 2: STATISTICAL INTERPRETATION
    # ==============================================================================

    faq_items.append(
        {
            "q": "What is the difference between F1-Score and Cohen's Kappa?",
            "a": (
                "<strong>F1-Score:</strong> Measures overlap on applied codes. Robust for rare codes.<br>"
                "<strong>Cohen's Kappa:</strong> Measures agreement accounting for chance. Requires True Negatives (silence) to be valid."
            ),
        }
    )

    faq_items.append(
        {
            "q": "Why is my Cohen's Kappa low even with high agreement?",
            "a": (
                "This is the <strong>Prevalence Paradox</strong>. If a code is very rare (e.g., 1% of text), "
                "Kappa penalizes even a single disagreement heavily. In these cases, rely on the F1-Score."
            ),
        }
    )

    return faq_items


def render_dashboard_html(context):
    """
    Returns the complete HTML string with all placeholders replaced by
    values found in the context dictionary.
    """
    html_template = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>IRR Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/exceljs/dist/exceljs.min.js"></script>
    <style>
        /* Default to Dark Theme */
        :root { 
            --bg-color: #121212; 
            --text-color: #e0e0e0; 
            --nav-bg: #1f1f1f; 
            --border: #333333; 
            --primary: #0d6efd; 
            --success: #198754; 
            --danger: #dc3545; 
            --card-bg: #1e1e1e; 
            --hover-bg: #2c2c2c;
        }
        
        /* Light Theme Override */
        [data-theme="light"] {
            --bg-color: #f8f9fa; 
            --text-color: #212529; 
            --nav-bg: #ffffff; 
            --border: #dee2e6; 
            --card-bg: #ffffff;
            --hover-bg: #e9ecef;
        }

        body { font-family: 'Segoe UI', sans-serif; background: var(--bg-color); color: var(--text-color); margin: 0; padding-bottom: 50px; transition: background 0.3s, color 0.3s; }
        
        .navbar { display: flex; justify-content: space-between; background: var(--nav-bg); padding: 10px 20px; border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 1000; align-items: center; }
        .nav-tabs { display: flex; gap: 10px; }
        .nav-btn { padding: 8px 16px; border: none; background: transparent; cursor: pointer; font-weight: 600; opacity: 0.7; color: var(--text-color); }
        .nav-btn.active { background: var(--primary); color: white; opacity: 1; border-radius: 4px; }
        .nav-btn:hover:not(.active) { background: var(--hover-bg); }

        .theme-toggle { background: transparent; border: 1px solid var(--border); color: var(--text-color); padding: 5px 10px; border-radius: 4px; cursor: pointer; }
        
        .nav-select { background: var(--nav-bg); color: var(--text-color); border: 1px solid var(--border); padding: 6px; border-radius: 4px; margin-left: 10px; cursor: pointer; }

        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .view-section { display: none; }
        .view-section.active { display: block; }

        .category-block { margin-top: 10px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 5px; overflow: hidden; }
        .category-header { padding: 10px; background: var(--hover-bg); cursor: pointer; font-weight: bold; display: flex; justify-content: space-between; border-bottom: 1px solid var(--border); }
        
        .code-list { display: none; padding-top: 5px; }
        .code-block { margin: 5px 15px; border-left: 2px solid var(--border); padding-left: 10px; }
        .code-header { 
            cursor: pointer; 
            padding: 10px 15px; 
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-left: 4px solid var(--primary); 
            border-radius: 4px; 
            font-weight: 600; 
            color: var(--text-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.2s ease;
        }
        .code-header:hover { background: var(--hover-bg); transform: translateY(-2px); border-color: var(--primary); }

        .segment-list { display: none; margin-left: 15px; border-left: 2px solid var(--border); }
        .segment { background: var(--card-bg); padding: 10px; margin-bottom: 8px; border-bottom: 1px solid var(--border); font-size: 0.95em; }
        
        .status-icon { float: right; font-size: 1.2em; }
        .status-agree { color: var(--success); }
        .status-disagree { color: var(--danger); }
        .status-ignored { color: #888; opacity: 0.6; } 
        .status-tn { color: #6c757d; font-style: italic; }
        .coder-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; color: #fff; font-weight: bold; }
        .meta-tag { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-right: 5px; background: #444; color: #ddd; }

        .irr-table { width: 100%; border-collapse: collapse; font-size: 0.9em; background: var(--card-bg); color: var(--text-color); }
        .irr-table th, .irr-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid var(--border); }
        .clickable-text { cursor: pointer; transition: color 0.2s; }
        .clickable-text:hover { color: var(--primary); text-decoration: underline; }
        
        .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
        .chart-card { background: var(--card-bg); padding: 15px; border-radius: 8px; border: 1px solid var(--border); height: 400px; display: flex; flex-direction: column; }
        .chart-container { flex: 1; position: relative; min-height: 0; width: 100%; }

        .controls { margin-bottom: 15px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .sticky-toolbar { position: -webkit-sticky; position: sticky; top: 57px; z-index: 990; background-color: var(--bg-color); padding: 10px 0; border-bottom: 1px solid var(--border); margin-top: -10px; }
        
        .report-pre { white-space: pre-wrap; font-family: monospace; background: var(--card-bg); color: var(--text-color); padding: 15px; border: 1px solid var(--border); border-radius: 5px; max-height: 600px; overflow-y: auto; }
        .sub-nav-btn { padding: 6px 12px; background: var(--card-bg); border: 1px solid var(--border); color: var(--text-color); cursor: pointer; margin-right: 5px; border-radius: 4px; }
        .sub-nav-btn.active { background: var(--primary); color: white; border-color: var(--primary); }

        /* Modal Styles */
        .modal { display: none; position: fixed; z-index: 2000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6); backdrop-filter: blur(2px); }
        .modal-content { background-color: var(--card-bg); margin: 2vh auto; padding: 0; border: 1px solid var(--border); width: 96%; height: 94vh; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); display: flex; flex-direction: column; }
        .modal-header { padding: 15px 20px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; background: var(--nav-bg); border-radius: 8px 8px 0 0; }
        .modal-body-container { display: flex; flex: 1; overflow: hidden; }
        .modal-sidebar { width: 280px; background: var(--nav-bg); border-right: 1px solid var(--border); overflow-y: auto; padding: 15px; flex-shrink: 0; }
        .modal-text-area { flex: 1; padding: 30px; overflow-y: auto; white-space: pre-wrap; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.8; font-size: 1.1em; color: var(--text-color); position: relative; }
        .modal-footer { padding: 15px 20px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end; gap: 10px; background: var(--nav-bg); border-radius: 0 0 8px 8px; }
        .close-modal { color: #aaa; font-size: 28px; font-weight: bold; cursor: pointer; }
        .close-modal:hover { color: var(--text-color); }
        
        .highlight-span { background-color: rgba(255, 255, 0, 0.15); border-bottom: 2px solid; cursor: pointer; transition: background 0.2s; border-radius: 2px; }
        .highlight-span:hover { background-color: rgba(255, 255, 0, 0.4); }
        .highlight-active { background-color: rgba(255, 255, 0, 0.6) !important; box-shadow: 0 0 10px rgba(255,255,0,0.5); }

        .sidebar-code-item { padding: 8px; border-bottom: 1px solid var(--border); font-size: 0.9em; cursor: pointer; border-left: 4px solid transparent; }
        .sidebar-code-item:hover { background: var(--hover-bg); }
        .sidebar-code-item.active { background: var(--hover-bg); border-left-color: var(--primary); }
        
        .coder-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; transition: background 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { opacity: 0.9; }
        .btn-secondary { background: var(--border); color: var(--text-color); }
        .btn-secondary:hover { background: #555; }
        .memo-block { margin-top: 4px; font-size: 0.85em; color: var(--text-color); opacity: 0.8; background: rgba(255, 255, 255, 0.05); padding: 4px 8px; border-left: 2px solid var(--primary); border-radius: 0 4px 4px 0; display: inline-block; }
        
        /* Codebook Table Styles */
        .def-table-container { overflow-x: auto; margin-top: 15px; }
        .def-table { width: 100%; border-collapse: collapse; font-size: 0.9em; background: var(--card-bg); color: var(--text-color); }
        .def-table th, .def-table td { padding: 8px; border: 1px solid var(--border); vertical-align: top; }
        .def-table th { background: var(--nav-bg); cursor: pointer; white-space: nowrap; position: sticky; top: 0; z-index: 10; }
        .def-table th:hover { background: var(--hover-bg); }
        
        .def-table textarea { background: transparent; border: none; color: inherit; width: 100%; font-family: inherit; font-size: inherit; resize: vertical; min-height: 60px; line-height: 1.4; }
        .def-table textarea:focus { outline: 1px solid var(--primary); background: rgba(255,255,255,0.05); }
        
        .col-narrow { width: 80px; min-width: 80px; white-space: nowrap; }
        .col-wide { min-width: 300px; white-space: normal; }
        .col-normal { min-width: 150px; }
        .action-cell { width: 50px; min-width: 50px !important; text-align: center; }
        .btn-sm { padding: 2px 8px; font-size: 0.8em; margin: 0 2px; }
        .btn-danger { background: var(--danger); color: white; border: none; cursor: pointer; border-radius: 3px; }
        .btn-save-mem { background: var(--primary); color: white; margin-right: 10px; }
        .btn-download { background: #444; color: white; border: 1px solid var(--border); margin-left: 5px; }
        .btn-download:hover { background: #555; }

        .report-textarea { width: 100%; height: 600px; background: var(--card-bg); color: var(--text-color); border: 1px solid var(--border); font-family: 'Segoe UI', monospace; padding: 15px; font-size: 1em; resize: vertical; white-space: pre-wrap; overflow-y: auto; }
        
        /* Modal Metadata */
        .modal-metadata { background: rgba(255, 255, 255, 0.05); padding: 10px 15px; border-bottom: 1px solid var(--border); font-size: 0.85em; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
        .meta-item { display: flex; flex-direction: column; }
        .meta-label { font-weight: bold; color: var(--primary); opacity: 0.8; font-size: 0.9em; }
        .meta-value { font-family: monospace; }
        
        /* Transcript Grid */
        .transcript-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 15px; margin-top: 15px; }
        .transcript-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 15px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; display: flex; align-items: center; gap: 15px; }
        .transcript-card:hover { transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.2); border-color: var(--primary); }
        .t-icon { font-size: 1.8em; color: var(--primary); opacity: 0.8; }
        .t-info { flex: 1; overflow: hidden; }
        .t-name { font-weight: 600; font-size: 1em; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .t-meta { font-size: 0.8em; opacity: 0.6; }

        /* FAQ */
        .faq-container { max-width: 900px; margin: 0 auto; }
        .faq-item { background: var(--card-bg); border: 1px solid var(--border); margin-bottom: 10px; border-radius: 6px; overflow: hidden; transition: border-color 0.2s; }
        .faq-item:hover { border-color: var(--primary); }
        .faq-question { padding: 15px 20px; cursor: pointer; font-weight: 600; display: flex; justify-content: space-between; align-items: center; background: rgba(255, 255, 255, 0.02); }
        .faq-question:after { content: '+'; font-size: 1.2em; font-weight: bold; color: var(--primary); }
        .faq-item.open .faq-question:after { content: '-'; }
        .faq-item.open .faq-question { border-bottom: 1px solid var(--border); background: var(--hover-bg); }
        .faq-answer { max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; padding: 0 20px; color: var(--text-color); opacity: 0.9; line-height: 1.6; }
        .faq-item.open .faq-answer { padding: 20px; max-height: 1000px; transition: max-height 0.5s ease-in; }
        .faq-search-container { margin-bottom: 30px; text-align: center; }
        #faq-search { width: 100%; max-width: 600px; padding: 12px 20px; border-radius: 25px; border: 1px solid var(--border); background: var(--card-bg); color: var(--text-color); font-size: 1.1em; transition: box-shadow 0.3s; }
        #faq-search:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 15px rgba(13, 110, 253, 0.2); }

        .filter-toggle-container { display: inline-flex; align-items: center; margin-right: 15px; background: var(--card-bg); padding: 5px 10px; border-radius: 4px; border: 1px solid var(--border); font-size: 0.9em; }
        .filter-toggle-container input { margin-right: 8px; cursor: pointer; }
        .filter-toggle-container label { cursor: pointer; user-select: none; }
    </style>
</head>
<body>

<nav class="navbar">
    <div style="font-weight: bold; display:flex; align-items:center; gap:15px;">
        <span>IRR Dashboard</span>
        <span style="font-size: 0.8em; font-weight: normal; opacity: 0.7; border: 1px solid var(--border); padding: 2px 8px; border-radius: 4px;">Method: {method_name}</span>
        <button class="theme-toggle" onclick="toggleTheme()" id="theme-btn">☀ Light Mode</button>
    </div>
    <div>
        <select id="participant-filter" class="nav-select" onchange="onParticipantSelect(this.value)">
            <option value="">Show All Participants</option>
        </select>
        <select id="coder-filter" class="nav-select" onchange="onCoderSelect(this.value)">
            <option value="">Show All Coders</option>
        </select>
    </div>
    <div class="nav-tabs">
        <button class="nav-btn active" onclick="switchTab('browser')" id="btn-browser">Browser</button>
        <button class="nav-btn" onclick="switchTab('analysis')" id="btn-analysis">Charts</button>
        <button class="nav-btn" onclick="switchTab('data')" id="btn-data">Analysis Details</button>
        <button class="nav-btn" onclick="switchTab('codebook')" id="btn-codebook" style="display:none;">Codebook definition</button>
        <button class="nav-btn" onclick="switchTab('transcripts')" id="btn-transcripts">Transcripts</button>
        <button class="nav-btn" onclick="switchTab('faq')" id="btn-faq">FAQ</button>
    </div>
</nav>

<div class="container">
    <div id="view-browser" class="view-section active">
        <div class="controls sticky-toolbar">
            <button onclick="expandAll()">Expand All</button>
            <button onclick="collapseAll()">Collapse All</button>
            <textarea id="search-box" placeholder="Filter text or search category:code... Use ';' to search multiple terms (e.g. 'code-a; code-b')" onkeyup="filterBrowser()" style="padding:5px; width:900px; height:36px; vertical-align:middle; resize:vertical; font-family:inherit;"></textarea>
            <button onclick="resetBrowserFilter()" style="font-size:0.8em; cursor:pointer;">Reset Filters</button>
        </div>
        <div id="browser-root"></div>
    </div>

    <div id="view-faq" class="view-section">
        <div class="faq-container">
            <h2 style="text-align: center; margin-bottom: 10px;">Research Protocol & Methodology FAQ</h2>
            <div class="faq-search-container">
                <input type="text" id="faq-search" placeholder="Search questions..." onkeyup="filterFAQ()">
            </div>
            <div id="faq-list"></div>
        </div>
    </div>

    <div id="view-analysis" class="view-section">
         <div class="charts-grid">
            <div class="chart-card">
                <h4>Category Distribution</h4>
                <div class="chart-container"><canvas id="chart-cat"></canvas></div>
            </div>
            <div class="chart-card">
                <div style="display:flex; justify-content:space-between">
                    <h4>Code Breakdown</h4>
                    <select id="cat-select" onchange="updateCodeChart()"></select>
                </div>
                <div class="chart-container"><canvas id="chart-code"></canvas></div>
            </div>
            <div class="chart-card">
                <h4>Top 15 Codes by Frequency</h4>
                <div class="chart-container"><canvas id="chart-top-codes"></canvas></div>
            </div>
            <div class="chart-card">
                <h4>Top 15 Codes by Disagreement Count</h4>
                <div class="chart-container"><canvas id="chart-top-disagreements"></canvas></div>
            </div>
            <div class="chart-card">
                <h4>Coder Activity Volume</h4>
                <div class="chart-container"><canvas id="chart-coder-vol"></canvas></div>
            </div>
            <div class="chart-card">
                <h4>Agreement vs. Disagreement by Category</h4>
                <div class="chart-container"><canvas id="chart-cat-agree"></canvas></div>
            </div>
        </div>
    </div>

    <div id="view-data" class="view-section">
        <div class="controls" style="border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 20px;">
            <strong>View: </strong>
            <button class="sub-nav-btn active" onclick="switchSubTab('table', this)">Data Table</button>
            <button class="sub-nav-btn" onclick="switchSubTab('notes1', this)">Merge Notes</button>
            <button class="sub-nav-btn" onclick="switchSubTab('notes2', this)">Agreement Stats</button>
            <button class="sub-nav-btn" onclick="switchSubTab('disagreements', this)">Disagreement Report</button>
            <button class="sub-nav-btn" onclick="switchSubTab('ignored', this)">Ignored Report</button>
        </div>

        <div id="sub-view-table" class="sub-view">
             <div class="controls" style="display:flex; align-items:center; flex-wrap:wrap; gap: 5px;">
                <strong>Filter: </strong>
                <button class="btn btn-sm btn-secondary" onclick="renderTable('all')">All Rows</button>
                <button class="btn btn-sm btn-success" onclick="renderTable('agree')">Agreements</button>
                <button class="btn btn-sm btn-danger" onclick="renderTable('disagree')">Disagreements</button>
                <button class="btn btn-sm btn-warning" onclick="renderTable('omission')" style="color:#000;">Omissions (ignored)</button>
                <button class="btn btn-sm" style="background:#6c757d; color:white;" onclick="renderTable('tn')">True Negatives</button>
                
                <span id="table-row-count" style="margin-left: auto; font-weight: bold; color: var(--primary); font-size: 0.9em;"></span>
                <button onclick="downloadTableCSV()" style="margin-left:15px;" class="btn btn-primary">Download CSV</button>
            </div>
            <div style="overflow-x:auto; margin-top: 10px;">
                <table class="irr-table">
                    <thead><tr><th>#</th><th>ID</th><th>P</th><th>Text</th><th>Code</th><th>Coders</th><th>Status</th></tr></thead>
                    <tbody id="table-body"></tbody>
                </table>
            </div>
        </div>
        
        <div id="sub-view-disagreements" class="sub-view" style="display:none;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                 <h3 style="margin:0">Disagreement Report</h3>
                 <button class="btn btn-primary" onclick="copyDisagreementReport()">Copy Report</button>
            </div>
            <textarea id="content-disagreements" class="report-textarea" readonly></textarea>
        </div>
        
        <div id="sub-view-ignored" class="sub-view" style="display:none;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                 <h3 style="margin:0">Ignored Segments Report</h3>
                 <button class="btn btn-primary" onclick="copyIgnoredReport()">Copy Report</button>
            </div>
            <textarea id="content-ignored" class="report-textarea" readonly></textarea>
        </div>

        <div id="sub-view-notes1" class="sub-view" style="display:none;">
            <div id="content-notes1" class="report-pre"></div>
        </div>
        <div id="sub-view-notes2" class="sub-view" style="display:none;">
            <div id="content-notes2" class="report-pre"></div>
        </div>
    </div>

    <div id="view-codebook" class="view-section">
        <div class="controls">
            <input type="text" id="codebook-search" placeholder="Search definitions..." onkeyup="renderCodebookTable()" style="padding: 8px; width: 300px; border-radius: 4px; border: 1px solid var(--border); background: var(--bg-color); color: var(--text-color);">
            <button class="btn btn-primary btn-save-mem" id="btn-save-edit" onclick="saveCurrentEdit()">Save current edit</button>
            <button class="btn btn-secondary" onclick="addCodebookRow()">+ Add Row</button>
            <button class="btn btn-download" onclick="exportCodebookCSV()">Download CSV</button>
            <button class="btn btn-download" onclick="exportCodebookXLSX()">Download Excel</button>
        </div>
        <p style="opacity: 0.7; font-size: 0.9em; margin-bottom: 10px;">
            Note: Edits made here are temporary (in-browser memory). Download the file to save permanently.
        </p>
        <div id="codebook-table-root" class="def-table-container"></div>
    </div>

    <div id="view-transcripts" class="view-section">
        <div id="transcript-grid" class="transcript-grid"></div>
        <ul id="transcript-list" style="display:none;"></ul>
        <button class="btn btn-primary" style="margin-top: 25px;" onclick="loadAllTranscripts()">Load All in New Window</button>
    </div>
    
    <div id="text-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Full Text View</h3>
                <span class="close-modal" onclick="closeTextModal()">&times;</span>
            </div>
            <div class="modal-body-container">
                <div class="modal-sidebar" id="modal-sidebar-content"></div>
                <div class="modal-text-area" id="modal-text-content"></div>
            </div>
        </div>
    </div>

    <div id="simple-text-modal" class="modal">
         <div class="modal-content" style="height: 70vh; margin: 5vh auto; width: 70%;">
            <div class="modal-header"><h3>Segment Detail</h3><span class="close-modal" onclick="closeSimpleTextModal()">&times;</span></div>
            <div id="simple-modal-meta" class="modal-metadata"></div>
            <div id="simple-modal-content" style="padding: 20px; overflow-y: auto; flex: 1; white-space: pre-wrap; font-size: 1.1em;"></div>
            <div class="modal-footer" style="justify-content: space-between;">
                <div>
                    <button class="btn btn-secondary" id="btn-prev-seg" onclick="navigateSimpleModal(-1)">Previous <span id="prev-id-display" style="font-size:0.8em; opacity:0.7"></span></button>
                    <button class="btn btn-secondary" id="btn-next-seg" onclick="navigateSimpleModal(1)">Next <span id="next-id-display" style="font-size:0.8em; opacity:0.7"></span></button>
                </div>
                <div>
                    <button class="btn btn-secondary" onclick="copySimpleModalText(this)">Copy Text</button>
                    <button class="btn btn-primary" onclick="closeSimpleTextModal()">Close</button>
                </div>
            </div>
         </div>
    </div>
</div>

<script>
    const RAW_DATA = {
        hierarchical: {hierarchical_json},
        analysis: {analysis_json},
        irrRecords: {irr_records_json},
        coders: {coders_json},
        participants: {participants_json},
        textReports: {reports_json},
        codebook: { columns: {codebook_columns_json}, rows: {codebook_rows_json} },
        transcriptFiles: {transcript_files_json},
        transcriptContents: {transcript_contents_json},
        faqData: {faq_json}
    };
    
    let DATA = JSON.parse(JSON.stringify(RAW_DATA));
    let chartInstances = {};
    let activeCodeBreakdown = null;

    document.addEventListener('DOMContentLoaded', () => {
        DATA.irrRecords = RAW_DATA.irrRecords;
        rebuildHierarchicalData();
        renderBrowser();
        renderReports(); 
        renderTable('all'); 
        renderFAQ();
        populateCoderDropdown();
        populateParticipantDropdown();
        
        if (DATA.codebook.columns && DATA.codebook.columns.length > 0) {
            document.getElementById('btn-codebook').style.display = 'block';
            renderCodebookTable();
        }

        const savedTab = localStorage.getItem('activeTab') || 'browser';
        switchTab(savedTab);
        activeCodeBreakdown = DATA.analysis.codeBreakdown;
    });
    
    function rebuildHierarchicalData() {
        const newHierarchy = {};
        // Define the specific buckets for the Master List
        const masterBuckets = {
            "Agreements": [],
            "Disagreements": [],
            "Omissions": [],
            "True Negatives": []
        };

        DATA.irrRecords.forEach(r => {
            // 1. Standard Category Parsing
            let cat = "Master List";
            let codeName = r.code;
            
            // Attempt to parse "Category: Code" format
            if (r.code && r.code.includes(':')) {
                const parts = r.code.split(':', 2);
                cat = parts[0].trim();
                codeName = parts[1].trim();
            } else if (r.code && r.code.toLowerCase() !== 'none' && r.code.trim() !== '') {
                // If it's a regular code without a category, put it in 'General'
                // unless it is explicitly 'None' (True Negative), which we handle separately
                cat = "General";
            }

            // Create the segment object
            const codersList = DATA.coders.filter(c => r[c] == 1);
            const segmentObj = {
                id: r.id,
                participant: r.p,
                text: r.text,
                memo: r.memo,
                coders: codersList,
                all_agree: r.all_agree,
                reporting_status: r.reporting_status,
                TN: r.TN
            };

            // 2. Populate Standard Hierarchy (Category -> Code)
            // We strictly exclude "Master List" here to prevent the "Nameless" or "None" 
            // categories from appearing as duplicates.
            if (cat !== "Master List") {
                if (!newHierarchy[cat]) newHierarchy[cat] = {};
                if (!newHierarchy[cat][codeName]) newHierarchy[cat][codeName] = [];
                newHierarchy[cat][codeName].push(segmentObj);
            }

            // 3. Populate Master List Sub-Categories
            const st = r.reporting_status;
            
            if (st === 'AGREE') {
                masterBuckets["Agreements"].push(segmentObj);
            } else if (st === 'DISAGREE') {
                masterBuckets["Disagreements"].push(segmentObj);
            } else if (st === 'IGNORED_OMISSION') {
                masterBuckets["Omissions"].push(segmentObj);
            } else if (st === 'TRUE_NEGATIVE' || st === 'IGNORED_TN') {
                masterBuckets["True Negatives"].push(segmentObj);
            }
        });

        // Assign the buckets to the hierarchy
        newHierarchy["Master List"] = masterBuckets;

        DATA.hierarchical = newHierarchy;
    }

    function switchTab(tabId) {
        localStorage.setItem('activeTab', tabId);
        document.querySelectorAll('.view-section').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));
        
        const targetView = document.getElementById('view-' + tabId);
        if(targetView) targetView.classList.add('active');
        
        const targetBtn = document.getElementById('btn-' + tabId);
        if(targetBtn) targetBtn.classList.add('active');

        if(tabId === 'analysis') setTimeout(initCharts, 50);
    }

    function switchSubTab(viewId, btnElement) {
        document.querySelectorAll('.sub-view').forEach(el => el.style.display = 'none');
        document.getElementById('sub-view-' + viewId).style.display = 'block';
        document.querySelectorAll('.sub-nav-btn').forEach(el => el.classList.remove('active'));
        btnElement.classList.add('active');
        if (viewId === 'disagreements') renderDisagreementReport();
        if (viewId === 'ignored') renderIgnoredReport();
    }

    function getCoderColor(name) {
        let index = DATA.coders.indexOf(name);
        if (index === -1) {
            let hash = 0;
            for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
            index = Math.abs(hash);
        }
        const hue = (index * 137.508) % 360;
        return `hsl(${hue}, 75%, 45%)`;
    }

    function populateCoderDropdown() {
        const select = document.getElementById('coder-filter');
        DATA.coders.sort().forEach(coder => {
            const opt = document.createElement('option');
            opt.value = coder; opt.innerText = coder; select.appendChild(opt);
        });
    }

    function populateParticipantDropdown() {
        const select = document.getElementById('participant-filter');
        DATA.participants.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p; opt.innerText = p; select.appendChild(opt);
        });
    }

    function onCoderSelect(val) { filterBrowser(null, 'text', false); updateCharts(); }
    function onParticipantSelect(val) { filterBrowser(null, 'text', false); updateCharts(); }

    function updateCharts() {
        const coderName = document.getElementById('coder-filter').value;
        const participantName = document.getElementById('participant-filter').value;
        const records = DATA.irrRecords.filter(r => {
            if (r.is_true_negative === 1) return false;
            const matchCoder = !coderName || r[coderName] === 1;
            const matchParticipant = !participantName || r.p === participantName;
            return matchCoder && matchParticipant;
        });

        const catCounts = {};
        const codeCountsByCat = {};
        const codeCountsOverall = {};
        const disagreeCounts = {};
        const coderVol = {};
        const catAgreeStats = {};

        records.forEach(r => {
            let cat = "Master List";
            let codeName = r.code;
            if (r.code.includes(':')) {
                const parts = r.code.split(':', 2);
                cat = parts[0].trim();
                codeName = parts[1].trim();
            }
            catCounts[cat] = (catCounts[cat] || 0) + 1;
            if (!codeCountsByCat[cat]) codeCountsByCat[cat] = {};
            codeCountsByCat[cat][codeName] = (codeCountsByCat[cat][codeName] || 0) + 1;
            codeCountsOverall[r.code] = (codeCountsOverall[r.code] || 0) + 1;
            if (r.all_agree === 0) disagreeCounts[r.code] = (disagreeCounts[r.code] || 0) + 1;
            DATA.coders.forEach(c => { if (r[c] === 1) coderVol[c] = (coderVol[c] || 0) + 1; });
            if (!catAgreeStats[cat]) catAgreeStats[cat] = { agree: 0, disagree: 0 };
            if (r.all_agree === 1) catAgreeStats[cat].agree++; else catAgreeStats[cat].disagree++;
        });

        activeCodeBreakdown = {};
        Object.keys(codeCountsByCat).forEach(cat => {
            activeCodeBreakdown[cat] = { labels: Object.keys(codeCountsByCat[cat]), data: Object.values(codeCountsByCat[cat]) };
        });

        updateChartData('chart-cat', Object.keys(catCounts), Object.values(catCounts));
        const topCodes = getTopN(codeCountsOverall, 15);
        updateChartData('chart-top-codes', topCodes.labels, topCodes.data);
        const topDis = getTopN(disagreeCounts, 15);
        updateChartData('chart-top-disagreements', topDis.labels, topDis.data);
        const topVol = getTopN(coderVol, 20);
        updateChartData('chart-coder-vol', topVol.labels, topVol.data);

        const sortedCats = Object.keys(catAgreeStats).sort();
        const chartAgree = chartInstances['chart-cat-agree']; 
        if (chartAgree) {
            chartAgree.data.labels = sortedCats;
            chartAgree.data.datasets[0].data = sortedCats.map(c => catAgreeStats[c].agree);
            chartAgree.data.datasets[1].data = sortedCats.map(c => catAgreeStats[c].disagree);
            chartAgree.update();
        }
        
        const catSelect = document.getElementById('cat-select');
        const currentVal = catSelect.value;
        catSelect.innerHTML = '';
        Object.keys(activeCodeBreakdown).sort().forEach(c => {
            const opt = document.createElement('option');
            opt.value = c; opt.innerText = c; catSelect.appendChild(opt);
        });
        if (currentVal && activeCodeBreakdown[currentVal]) catSelect.value = currentVal;
        updateCodeChart();
    }

    function getTopN(sourceObj, n) {
        const sorted = Object.entries(sourceObj).sort((a, b) => b[1] - a[1]).slice(0, n);
        return { labels: sorted.map(x => x[0]), data: sorted.map(x => x[1]) };
    }

    function updateChartData(chartKey, labels, data) {
        let chart = chartInstances[chartKey];
        if (!chart) { chart = Chart.getChart(chartKey); if(chart) chartInstances[chartKey] = chart; }
        if (chart) { chart.data.labels = labels; chart.data.datasets[0].data = data; chart.update(); }
    }

    function renderBrowser() {
        const root = document.getElementById('browser-root');
        root.innerHTML = '';
        Object.keys(DATA.hierarchical).sort().forEach(cat => {
            const catBlock = document.createElement('div');
            catBlock.className = 'category-block';
            catBlock.setAttribute('data-cat', cat);

            const validCodes = [];
            const codesInCat = Object.keys(DATA.hierarchical[cat]);
            codesInCat.forEach(code => {
                let segments = DATA.hierarchical[cat][code];
                if (segments.length > 0) validCodes.push({code, segments});
            });

            if (validCodes.length === 0) return;

            // Header Calculation: Only count relevant items for the % display in the header
            const header = document.createElement('div');
            header.className = 'category-header';
            let totalSegs = 0;      // Display count (all visible rows)
            let statsTotal = 0;     // Statistical count (valid for % calc)
            let totalAgree = 0;

            validCodes.forEach(item => {
                item.segments.forEach(seg => { 
                    totalSegs++; // Count ALL visible segments for the UI label
                    
                    // EDIT: Strictly follow the Reporting Status. 
                    // If status is 'IGNORED_TN' or 'IGNORED_OMISSION', it must NOT contribute to statsTotal.
                    // This ensures Method A/B calculations are correct in the UI.
                    if (seg.reporting_status === 'AGREE' || seg.reporting_status === 'DISAGREE' || seg.reporting_status === 'TRUE_NEGATIVE') {
                        statsTotal++;
                        if(seg.reporting_status === 'AGREE' || seg.reporting_status === 'TRUE_NEGATIVE') totalAgree++; 
                    }
                });
            });

            // Calculate Disagree based on the STATS total, not the display total
            const totalDisagree = statsTotal - totalAgree;
            const catPct = statsTotal > 0 ? ((totalAgree / statsTotal) * 100).toFixed(1) : "0.0";
            let catPctColor = parseFloat(catPct) >= 80 ? 'var(--success)' : (parseFloat(catPct) < 60 ? 'var(--primary)' : '#fd7e14');

            header.innerHTML = `
                <span style="flex: 1;">${cat}</span> 
                <span style="opacity: 0.8; font-weight: normal;">(${validCodes.length} codes, ${totalSegs} segments)</span>
                <span style="flex: 1; display: flex; justify-content: flex-end; align-items: center; gap: 10px; font-family: monospace; font-size: 0.9em; font-weight: normal;">
                    <span style="color: ${catPctColor}; font-weight: bold;">${catPct}%</span>
                    <span style="opacity: 0.3">|</span>
                    <span style="color: var(--success)">Agr: ${totalAgree}</span>
                    <span style="color: var(--danger)">Dis: ${totalDisagree}</span>
                </span>`;
            header.onclick = () => toggleDisplay(header.nextElementSibling);
            catBlock.appendChild(header);

            const codeList = document.createElement('div');
            codeList.className = 'code-list';

            validCodes.forEach(item => {
                const code = item.code;
                const segments = item.segments;
                const codeBlock = document.createElement('div');
                codeBlock.className = 'code-block';
                codeBlock.setAttribute('data-code', code);
                
                // --- Code Header Stats Calculation ---
                let displayTotal = 0;
                let statsTotal = 0;
                let agreeCount = 0;
                item.segments.forEach(seg => {
                        displayTotal++; // Count ALL visible segments
                        
                        // EDIT: Same fix for Code-level headers. Exclude ignored types from percentages.
                        if (seg.reporting_status === 'AGREE' || seg.reporting_status === 'DISAGREE' || seg.reporting_status === 'TRUE_NEGATIVE') {
                        statsTotal++;
                        if(seg.reporting_status === 'AGREE' || seg.reporting_status === 'TRUE_NEGATIVE') agreeCount++; 
                    }
                });
                const disagreeCount = statsTotal - agreeCount;
                const pct = statsTotal > 0 ? ((agreeCount / statsTotal) * 100).toFixed(1) : "0.0";
                let pctColor = parseFloat(pct) >= 80 ? 'var(--success)' : (parseFloat(pct) < 60 ? 'var(--primary)' : '#fd7e14');
                const cHeader = document.createElement('div');
                cHeader.className = 'code-header';
                cHeader.innerHTML = `
                    <span style="flex: 1; text-align: left; overflow: hidden; text-overflow: ellipsis; margin-right: 10px;">${code}</span>
                    <span style="opacity: 0.8; font-weight: normal;">(${displayTotal} segments)</span>
                    <span style="flex: 1; display: flex; justify-content: flex-end; align-items: center; gap: 10px; font-family: monospace; font-size: 0.9em;">
                        <span style="color: ${pctColor}; font-weight: bold;">${pct}%</span>
                        <span style="opacity: 0.3">|</span>
                        <span style="color: var(--success)">Agr: ${agreeCount}</span>
                        <span style="color: var(--danger)">Dis: ${disagreeCount}</span>
                    </span>`;
                cHeader.onclick = () => toggleDisplay(cHeader.nextElementSibling);
                codeBlock.appendChild(cHeader);

                const segList = document.createElement('div');
                segList.className = 'segment-list';
                item.segments.forEach(seg => {
                    const div = document.createElement('div');
                    div.className = 'segment';
                    div.setAttribute('data-coders', seg.coders.join(','));
                    div.setAttribute('data-participant', seg.participant);
                    let statusHtml = '';
                    const st = seg.reporting_status;
                    
                    // Logic: Green (success) for accepted/agreement, Red (danger) for disagreement
                    if (st === 'AGREE') {
                        statusHtml = '<span class="status-icon status-agree">&#10003;</span>'; // Check
                    } else if (st === 'DISAGREE') {
                        statusHtml = '<span class="status-icon status-disagree">&#10007;</span>'; // X
                    } else if (st === 'TRUE_NEGATIVE') {
                        // Method C: TN is an Agreement. Add Checkmark!
                        statusHtml = '<span class="status-icon status-tn" title="True Negative (Agreement)" style="color:var(--success); font-weight:bold;">[TN] &#10003;</span>';
                    } else if (st === 'IGNORED_OMISSION') {
                        statusHtml = '<span class="status-icon status-ignored" title="Omission (Ignored by Method)" style="color:var(--text-color); font-weight:bold;">&ominus;</span>';
                    } else if (st === 'IGNORED_TN') {
                        // Method A/B: TN is Ignored. No Checkmark.
                        statusHtml = '<span class="status-icon status-tn" title="True Negative (Ignored by Method)" style="color:#6c757d;">[TN]</span>';
                    }

                    let badges = '';
                    seg.coders.forEach(c => badges += `<span class="coder-tag" style="background-color:${getCoderColor(c)}">${c}</span>`);
                    const memoHtml = seg.memo ? `<div class="memo-block">📝 <strong>Memo:</strong> ${escapeHtml(seg.memo)}</div>` : '';
                    div.innerHTML = `<div style="margin-bottom:4px; color:#666;"><span class="meta-tag">${seg.participant}</span>${badges}${statusHtml}</div><div style="font-style:italic;">"${escapeHtml(seg.text)}"</div>${memoHtml}`;
                    segList.appendChild(div);
                });
                codeBlock.appendChild(segList);
                codeList.appendChild(codeBlock);
            });
            catBlock.appendChild(codeList);
            root.appendChild(catBlock);
        });
    }

    function toggleDisplay(el) { el.style.display = (el.style.display === 'block') ? 'none' : 'block'; }
    function expandAll() { 
        document.querySelectorAll('.category-block').forEach(block => {
             block.querySelector('.code-list').style.display = 'block';
             block.querySelectorAll('.segment-list').forEach(s => s.style.display = 'block');
        });
    }
    function collapseAll() { document.querySelectorAll('.code-list, .segment-list').forEach(e => e.style.display = 'none'); }
    function resetBrowserFilter() {
        document.getElementById('search-box').value = "";
        document.getElementById('coder-filter').value = ""; 
        document.getElementById('participant-filter').value = ""; 
        filterBrowser(null, "text", false);
    }

    function filterBrowser(filterVal = null, type = 'text', switchView = true) {
        if (type === 'text' && filterVal === null) filterVal = document.getElementById('search-box').value;
        if (type !== 'text') {
            document.getElementById('search-box').value = "";
            document.getElementById('coder-filter').value = "";
            document.getElementById('participant-filter').value = "";
            if (switchView) switchTab('browser');
        }

        const rawTerms = (filterVal || "").toLowerCase().split(';');
        const searchTerms = rawTerms.map(t => t.trim()).filter(t => t.length > 0);
        const isSearchEmpty = searchTerms.length === 0;
        const selectedCoder = document.getElementById('coder-filter').value;
        const selectedParticipant = document.getElementById('participant-filter').value;

        document.querySelectorAll('.category-block').forEach(block => {
            const catName = block.getAttribute('data-cat');
            if (type === 'category') {
                if (catName === filterVal) {
                    block.style.display = 'block';
                    expandBlock(block);
                    block.scrollIntoView({behavior: "smooth"});
                } else block.style.display = 'none';
                return;
            }
            if (type === 'code') {
                let targetCode = filterVal;
                let targetCat = null;
                if (filterVal.includes(':')) {
                    const parts = filterVal.split(':', 2);
                    targetCat = parts[0].trim();
                    targetCode = parts[1].trim();
                }
                if (targetCat && catName !== targetCat) { block.style.display = 'none'; return; }
                const codeBlocks = block.querySelectorAll('.code-block');
                let hasMatch = false;
                codeBlocks.forEach(cb => {
                    if (cb.getAttribute('data-code') === targetCode) {
                        cb.style.display = 'block';
                        cb.querySelector('.segment-list').style.display = 'block';
                        cb.querySelectorAll('.segment').forEach(s => s.style.display = 'block');
                        hasMatch = true;
                    } else cb.style.display = 'none';
                });
                if (hasMatch) { block.style.display = 'block'; block.querySelector('.code-list').style.display = 'block'; if(targetCat) block.scrollIntoView({behavior: "smooth"}); }
                else block.style.display = 'none';
                return;
            }

            let categoryHasVisibleContent = false;
            block.querySelectorAll('.code-block').forEach(cb => {
                const codeName = cb.getAttribute('data-code');
                const contentMatchCode = searchTerms.some(term => codeName.toLowerCase().includes(term));
                let codeHasVisibleContent = false;
                cb.querySelectorAll('.segment').forEach(seg => {
                    const segCoders = (seg.getAttribute('data-coders') || "").split(',');
                    const segParticipant = seg.getAttribute('data-participant');
                    const coderMatches = !selectedCoder || segCoders.includes(selectedCoder);
                    const participantMatches = !selectedParticipant || segParticipant === selectedParticipant;
                    const segTextRaw = seg.innerText.toLowerCase();
                    const textMatches = isSearchEmpty || searchTerms.some(term => segTextRaw.includes(term));
                    
                    if (coderMatches && participantMatches && (textMatches || contentMatchCode)) {
                        seg.style.display = 'block';
                        codeHasVisibleContent = true;
                    } else seg.style.display = 'none';
                });

                if (codeHasVisibleContent) {
                    cb.style.display = 'block';
                    cb.querySelector('.segment-list').style.display = 'block';
                    categoryHasVisibleContent = true;
                } else cb.style.display = 'none';
            });
            if (categoryHasVisibleContent) { block.style.display = 'block'; block.querySelector('.code-list').style.display = 'block'; }
            else block.style.display = 'none';
        });
    }

    function expandBlock(block) {
        block.querySelector('.code-list').style.display = 'block';
        block.querySelectorAll('.code-block').forEach(cb => {
            cb.style.display = 'block';
            cb.querySelector('.segment-list').style.display = 'block';
            cb.querySelectorAll('.segment').forEach(s => s.style.display = 'block');
        });
    }
    
    function initCharts() {
        if (chartInstances['chart-cat']) return;
        
        const ctxCat = document.getElementById('chart-cat');
        if(ctxCat) {
            chartInstances['chart-cat'] = new Chart(ctxCat, {
                type: 'bar',
                data: { labels: DATA.analysis.categoryDistribution.labels, datasets: [{ label: 'Segments', data: DATA.analysis.categoryDistribution.data, backgroundColor: '#0d6efd' }] },
                options: { responsive: true, maintainAspectRatio: false, onClick: (e, elements) => { if (elements.length > 0) filterBrowser(DATA.analysis.categoryDistribution.labels[elements[0].index], 'category'); } }
            });
        }
        
        const ctxTopCodes = document.getElementById('chart-top-codes');
        if(ctxTopCodes) {
             chartInstances['chart-top-codes'] = new Chart(ctxTopCodes, { 
                type: 'bar',
                data: { labels: DATA.analysis.topCodes.labels, datasets: [{ label: 'Frequency', data: DATA.analysis.topCodes.data, backgroundColor: '#6610f2' }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, onClick: (e, elements) => { if (elements.length > 0) filterBrowser(DATA.analysis.topCodes.labels[elements[0].index], 'code'); } }
            });
        }
        const ctxTopDis = document.getElementById('chart-top-disagreements');
        if(ctxTopDis) {
            chartInstances['chart-top-disagreements'] = new Chart(ctxTopDis, { 
                type: 'bar',
                data: { labels: DATA.analysis.topDisagreements.labels, datasets: [{ label: 'Disagreements', data: DATA.analysis.topDisagreements.data, backgroundColor: '#dc3545' }] },
                options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, onClick: (e, elements) => { if (elements.length > 0) filterBrowser(DATA.analysis.topDisagreements.labels[elements[0].index], 'code'); } }
            });
        }
        const ctxCoder = document.getElementById('chart-coder-vol');
        if(ctxCoder) {
            const datasets = [];
            const rawData = DATA.analysis.coderVolume.rawData;
            if (rawData && rawData.some(x => x > 0)) datasets.push({ label: 'Raw Input Events', data: rawData, backgroundColor: '#6c757d', order: 2 });
            datasets.push({ label: 'Merged Segments (Final)', data: DATA.analysis.coderVolume.data, backgroundColor: '#fd7e14', order: 1 });
            chartInstances['chart-coder-vol'] = new Chart(ctxCoder, { 
                type: 'bar',
                data: { labels: DATA.analysis.coderVolume.labels, datasets: datasets },
                options: { 
                    responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
                    onClick: (e, elements) => { 
                        if (elements.length > 0) {
                            const selectedCoder = DATA.analysis.coderVolume.labels[elements[0].index];
                            document.getElementById('coder-filter').value = selectedCoder;
                            onCoderSelect(selectedCoder);
                        }
                    } 
                }
            });
        }
        const ctxCatAgree = document.getElementById('chart-cat-agree');
        if(ctxCatAgree) {
            chartInstances['chart-cat-agree'] = new Chart(ctxCatAgree, { 
                type: 'bar',
                data: {
                    labels: DATA.analysis.categoryAgreement.labels,
                    datasets: [ { label: 'Agree', data: DATA.analysis.categoryAgreement.agree, backgroundColor: '#198754' }, { label: 'Disagree', data: DATA.analysis.categoryAgreement.disagree, backgroundColor: '#dc3545' } ]
                },
                options: { responsive: true, maintainAspectRatio: false, scales: { x: { stacked: true }, y: { stacked: true } }, onClick: (e, elements) => { if (elements.length > 0) filterBrowser(DATA.analysis.categoryAgreement.labels[elements[0].index], 'category'); } }
            });
        }
        
        const catSelect = document.getElementById('cat-select');
        catSelect.innerHTML = '';
        Object.keys(DATA.analysis.codeBreakdown).sort().forEach(c => {
            const opt = document.createElement('option');
            opt.value = c; opt.innerText = c; catSelect.appendChild(opt);
        });
        updateCodeChart();
    }
    
    function updateCodeChart() {
        const cat = document.getElementById('cat-select').value;
        if(!cat || !activeCodeBreakdown) return;
        const data = activeCodeBreakdown[cat];
        if (!data) return; 
        const ctxCode = document.getElementById('chart-code');
        if(!ctxCode) return;
        if (chartInstances['code']) chartInstances['code'].destroy();
        chartInstances['code'] = new Chart(ctxCode, {
            type: 'bar',
            data: { labels: data.labels, datasets: [{ label: `Codes in ${cat}`, data: data.data, backgroundColor: '#198754' }] },
            options: { responsive: true, maintainAspectRatio: false, onClick: (e, elements) => { if (elements.length > 0) filterBrowser(data.labels[elements[0].index], 'code'); } }
        });
    }

    function renderTable(filterType) {
        currentTableFilter = filterType;
        const body = document.getElementById('table-body');
        const countLabel = document.getElementById('table-row-count');
        body.innerHTML = '';
        
        // 1. Base Data Filter
        let rawData = [...DATA.irrRecords];

        if (filterType === 'agree') {
            rawData = rawData.filter(r => r.reporting_status === 'AGREE');
        } 
        else if (filterType === 'disagree') {
            rawData = rawData.filter(r => r.reporting_status === 'DISAGREE');
        } 
        else if (filterType === 'omission') {
            rawData = rawData.filter(r => r.reporting_status === 'IGNORED_OMISSION');
        } 
        else if (filterType === 'tn') {
            rawData = rawData.filter(r => r.reporting_status === 'TRUE_NEGATIVE' || r.reporting_status === 'IGNORED_TN' || r.TN === 1);
        }
        
        // Set global data to filtered array (Ungrouped)
        currentTableData = rawData;

        // Update Label
        if(countLabel) countLabel.innerText = `Showing: ${rawData.length} rows`;
        
        // 2. Render Raw Rows (Matches CSV exactly)
        rawData.forEach((item, index) => {
            const tr = document.createElement('tr');
            
            // Calculate active coders for this specific row
            const activeCoders = DATA.coders.filter(c => item[c] === 1);
            const activeStr = activeCoders.sort().join(", ");
            
            // Format Code with pct
            let pctColor = '#666';
            const pctVal = parseFloat(DATA.analysis.codeStats[item.code] || 0);
            if (!isNaN(pctVal)) { 
                if (pctVal >= 80) pctColor = 'var(--success)'; 
                else if (pctVal < 60) pctColor = 'var(--danger)'; 
                else pctColor = 'var(--primary)'; 
            }
            
            const codeHtml = `
                <strong>${item.code}</strong> 
                <span style="font-size:0.75em; color:${pctColor}; font-weight:bold; margin-left:4px;">${DATA.analysis.codeStats[item.code] || "N/A"}</span>
            `;

            // Status Icon
            let statusIcon = '';
            const st = item.reporting_status;
            
            if (st === 'AGREE') statusIcon = '<span class="status-agree">✔</span>';
            else if (st === 'DISAGREE') statusIcon = '<span class="status-disagree">✘</span>';
            else if (st === 'IGNORED_OMISSION') statusIcon = '<span style="color:var(--text-color); font-weight:bold; font-size:1.2em;">&ominus;</span>';
            else if (st === 'TRUE_NEGATIVE') {
                // Method C Agreement (Green TN + Check)
                statusIcon = '<span class="status-tn" style="color:var(--success); font-weight:bold;">[TN] <span class="status-agree">✔</span></span>';
            }
            else if (st === 'IGNORED_TN') { 
                // Method A/B Ignored (Grey TN, no check)
                statusIcon = '<span class="status-tn" style="color:#6c757d;">[TN]</span>';
            }
            else statusIcon = '<span class="status-ignored">-</span>';

            tr.innerHTML = `
                <td>${index + 1}</td>
                <td>${item.id}</td>
                <td>${item.p}</td>
                <td class="clickable-text" style="max-width: 40vw; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" onclick="openSimpleTextModal(${index})">${escapeHtml(item.text)}</td>
                <td>${codeHtml}</td>
                <td>${activeStr}</td>
                <td style="text-align:center; white-space:nowrap;">${statusIcon}</td>
            `;
            body.appendChild(tr);
        });
    }
    
    function renderDisagreementReport() {
        const reportArea = document.getElementById('content-disagreements');
        if (!reportArea) return;
        const validRecords = DATA.irrRecords.filter(r => r.is_true_negative !== 1);
        const grouped = {};
        
        validRecords.forEach(r => {
            const key = r.text;
            // FIX: Initialize object AND coder arrays only once per text
            if (!grouped[key]) {
                grouped[key] = { text: r.text, coderData: {}, hasDisagreement: false };
                DATA.coders.forEach(c => grouped[key].coderData[c] = []);
            }
            
            // Check if this specific row represents a disagreement
            if (r.reporting_status === 'DISAGREE') {
                grouped[key].hasDisagreement = true;
            }
            
            // Collect code data from ALL rows associated with this text
            DATA.coders.forEach(coder => {
                if (r[coder] === 1) {
                    // Prevent duplicates if multiple rows have same code
                    if (!grouped[key].coderData[coder].includes(r.code)) {
                        grouped[key].coderData[coder].push(r.code);
                    }
                }
            });
        });

        // Filter: Only keep texts that were flagged as having a disagreement
        const disagreementList = Object.values(grouped).filter(item => item.hasDisagreement);
        
        let reportText = `#### Disagreement Report (Method: {method_name})\n`;
        reportText += `Unique Disagreement Segments: ${disagreementList.length}\n\n`;
        
        disagreementList.forEach((item, idx) => {
            reportText += `${idx + 1}. "${item.text}"\n`;
            DATA.coders.forEach(coder => {
                const codes = item.coderData[coder];
                if (codes.length > 0) reportText += `${coder}: ${codes.map(c => `\`${c}\``).join(', ')}\n`;
            });
            reportText += `\n`;
        });
        if (disagreementList.length === 0) reportText += "No disagreements found.";
        reportArea.value = reportText;
    }

    function renderIgnoredReport() {
        const reportArea = document.getElementById('content-ignored');
        if (!reportArea) return;
        // Use all records to ensure we catch 'IGNORED_OMISSION'
        const validRecords = DATA.irrRecords;
        
        const grouped = {};
        
        validRecords.forEach(r => {
            const key = r.text;
            // FIX: Initialize once
            if (!grouped[key]) {
                grouped[key] = { text: r.text, coderData: {}, isIgnored: false };
                DATA.coders.forEach(c => grouped[key].coderData[c] = []);
            }
            
            if (r.reporting_status === 'IGNORED_OMISSION') {
                grouped[key].isIgnored = true;
            }
            
            DATA.coders.forEach(coder => {
                if (r[coder] === 1) {
                    if (!grouped[key].coderData[coder].includes(r.code)) {
                        grouped[key].coderData[coder].push(r.code);
                    }
                }
            });
        });

        const ignoredList = Object.values(grouped).filter(item => item.isIgnored);
        let reportText = `#### Ignored Segments Report (Method: {method_name})\n`;
        reportText += `Unique Ignored Segments: ${ignoredList.length}\n\n`;

        ignoredList.forEach((item, idx) => {
            reportText += `${idx + 1}. "${item.text}"\n`;
            DATA.coders.forEach(coder => {
                const codes = item.coderData[coder];
                if (codes.length > 0) reportText += `${coder}: ${codes.map(c => `\`${c}\``).join(', ')}\n`;
            });
            reportText += `\n`;
        });
        if (ignoredList.length === 0) reportText += "No ignored segments found (or method does not ignore omissions).";
        reportArea.value = reportText;
    }

    function copyDisagreementReport() {
        const copyText = document.getElementById("content-disagreements");
        copyText.select();
        document.execCommand("copy");
        alert("Copied!");
    }
    
    function copyIgnoredReport() {
        const copyText = document.getElementById("content-ignored");
        copyText.select();
        document.execCommand("copy");
        alert("Copied!");
    }

    // SIMPLE MODAL LOGIC
    let currentModalIndex = 0;
    let currentTableData = []; // This now holds grouped objects, not raw CSV rows

    function openSimpleTextModal(index) {
        currentModalIndex = index; 
        updateSimpleModalContent();
        document.getElementById('simple-text-modal').style.display = 'block'; 
        document.body.style.overflow = 'hidden';
    }

    function updateSimpleModalContent() {
        if (currentModalIndex < 0 || currentModalIndex >= currentTableData.length) return;
        const item = currentTableData[currentModalIndex]; 
        
        const metaDiv = document.getElementById('simple-modal-meta');
        const contentDiv = document.getElementById('simple-modal-content');
        const prevBtn = document.getElementById('btn-prev-seg');
        const nextBtn = document.getElementById('btn-next-seg');
        const prevDisplay = document.getElementById('prev-id-display');
        const nextDisplay = document.getElementById('next-id-display');
        
        const activeCoders = DATA.coders.filter(c => item[c] === 1);
        const activeStr = activeCoders.sort().join(", ");
        
        metaDiv.innerHTML = `
            <div class="meta-item"><span class="meta-label">Row #</span><span class="meta-value">${currentModalIndex + 1}</span></div>
            <div class="meta-item"><span class="meta-label">ID</span><span class="meta-value">${item.id}</span></div>
            <div class="meta-item"><span class="meta-label">Participant</span><span class="meta-value">${item.p}</span></div>
            <div class="meta-item"><span class="meta-label">Code</span><span class="meta-value" style="font-size:0.9em;">${item.code}</span></div>
            <div class="meta-item"><span class="meta-label">Active Coders</span><span class="meta-value">${activeStr || "None"}</span></div>
            <div class="meta-item"><span class="meta-label">Status</span><span class="meta-value">${item.reporting_status}</span></div>
        `;
        contentDiv.innerText = item.text;

        // ... (rest of function remains the same)
        if (currentModalIndex <= 0) { 
            prevBtn.disabled = true; 
            prevDisplay.innerText = ""; 
        } else { 
            prevBtn.disabled = false; 
            prevDisplay.innerText = `(Row ${currentModalIndex})`; 
        }
        
        if (currentModalIndex >= currentTableData.length - 1) { 
            nextBtn.disabled = true; 
            nextDisplay.innerText = ""; 
        } else { 
            nextBtn.disabled = false; 
            nextDisplay.innerText = `(Row ${currentModalIndex + 2})`; 
        }
    }
    
    function navigateSimpleModal(direction) {
        const newIndex = currentModalIndex + direction;
        if (newIndex >= 0 && newIndex < currentTableData.length) { 
            currentModalIndex = newIndex; 
            updateSimpleModalContent(); 
        }
    }
    
    function copySimpleModalText(btn) {
        const content = document.getElementById('simple-modal-content').innerText;
        navigator.clipboard.writeText(content).then(() => { btn.innerText = "Copied!"; setTimeout(() => btn.innerText = "Copy Text", 1500); });
    }
    
    function closeSimpleTextModal() { document.getElementById('simple-text-modal').style.display = 'none'; document.body.style.overflow = 'auto'; }
    function closeTextModal() { document.getElementById('text-modal').style.display = 'none'; document.body.style.overflow = 'auto'; }
    function openTextModal() { document.getElementById('text-modal').style.display = 'block'; document.body.style.overflow = 'hidden'; }

    function loadAllTranscripts() {
        if (!confirm(`Are you sure you want to load ${DATA.transcriptFiles.length} transcripts? This will open a new window and could freeze your browser if files are large.`)) {
            return;
        }

        const newWindow = window.open('', '_blank');
        newWindow.document.write(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <title>All Transcripts</title>
                <style>body { font-family: monospace; white-space: pre-wrap; margin: 20px; }</style>
            </head>
            <body>
                <h1>Loading All Transcripts...</h1>
            </body>
            </html>
        `);

        // We can't fetch all content synchronously or it will block the UI thread.
        // For simplicity (and since this is a user-initiated action), we'll do sequential fetch/write.
        
        let allContent = '';
        let loadedCount = 0;
        const totalFiles = DATA.transcriptFiles.length;

        function fetchAndAppend(index) {
            if (index >= totalFiles) {
                // Final render
                newWindow.document.body.innerHTML = allContent;
                return;
            }

            const fileName = DATA.transcriptFiles[index];
            const filePath = `transcripts/${fileName}`;
            
            fetch(filePath)
                .then(response => {
                    if (!response.ok) throw new Error(`Status ${response.status}`);
                    return response.text();
                })
                .then(text => {
                    loadedCount++;
                    newWindow.document.body.innerHTML = `<h1>Loaded ${loadedCount}/${totalFiles} Transcripts...</h1>`;
                    allContent += `\n\n--- FILE: ${fileName} ---\n\n${text}`;
                    fetchAndAppend(index + 1);
                })
                .catch(error => {
                    loadedCount++;
                    newWindow.document.body.innerHTML = `<h1>Loaded ${loadedCount}/${totalFiles} Transcripts (Error on ${fileName})...</h1>`;
                    allContent += `\n\n--- ERROR Loading FILE: ${fileName} ---\n\n${error.message}\n`;
                    fetchAndAppend(index + 1);
                });
        }

        fetchAndAppend(0);
    }

    function copyModalText() {
        const content = document.getElementById('modal-text-content').innerText;
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(onCopySuccess);
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = content;
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                onCopySuccess();
            } catch (err) {
                console.error('Copy failed', err);
            }
            document.body.removeChild(textArea);
        }
    }

    function onCopySuccess() {
        const btn = document.getElementById('copy-btn');
        const original = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = original, 2000);
    }

    function downloadTableCSV() {
        // Updated to handle raw row structure (currentTableData is now raw records)
        let data = currentTableData; 
        const headers = ['ID', 'Participant', 'Text', 'Code', 'Active_Coders', 'Reporting_Status'];
        const csvRows = [headers.join(',')];

        data.forEach(item => {
            const activeCoders = DATA.coders.filter(c => item[c] === 1);
            const activeStr = activeCoders.sort().join("+");

            const row = [
                item.id,
                item.p,
                escapeCsv(item.text),
                escapeCsv(item.code),
                escapeCsv(activeStr),
                item.reporting_status
            ];
            csvRows.push(row.join(','));
        });

        const csvString = csvRows.join('\n');
        const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", `irr_data_${currentTableFilter}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    function escapeCsv(text) {
        if (text === null || text === undefined) return "";
        let str = String(text);
        if (str.includes('"') || str.includes(',') || str.includes('\n')) {
            str = '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }

    function copyElementText(elementId, btn) {
        const content = document.getElementById(elementId).innerText;
        const originalText = btn.innerText;
        
        const showSuccess = () => {
            btn.innerText = 'Copied!';
            setTimeout(() => btn.innerText = originalText, 2000);
        };

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(content).then(showSuccess);
        } else {
            const textArea = document.createElement("textarea");
            textArea.value = content;
            textArea.style.position = "fixed";
            textArea.style.left = "-9999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                showSuccess();
            } catch (err) {
                console.error('Copy failed', err);
                alert("Copy failed. Please select text manually.");
            }
            document.body.removeChild(textArea);
        }
    }

    window.onclick = function(event) {
        const modal = document.getElementById('text-modal');
        const simpleModal = document.getElementById('simple-text-modal');
        if (event.target == modal) closeTextModal();
        if (event.target == simpleModal) closeSimpleTextModal();
    }

    function renderReports() {
        const notes1 = DATA.textReports.notes1 || "No merge notes available.";
        const notes2 = DATA.textReports.notes2 || "No agreement stats available.";
        const el1 = document.getElementById('content-notes1'); if(el1) el1.innerText = notes1;
        const el2 = document.getElementById('content-notes2'); if(el2) el2.innerText = notes2;
        renderTranscriptList();
    }
    
    function renderTranscriptList() {
        const grid = document.getElementById('transcript-grid');
        const input = document.getElementById('transcript-search');
        if (!grid) return;
        const searchTerm = (input ? input.value : '').toLowerCase();
        grid.innerHTML = '';
        if (DATA.transcriptFiles.length === 0) { grid.innerHTML = '<div style="opacity:0.7; padding:15px;">No transcript files found.</div>'; return; }
        const filtered = DATA.transcriptFiles.filter(f => f.toLowerCase().includes(searchTerm));
        if (filtered.length === 0) { grid.innerHTML = '<div style="opacity:0.7; padding:15px;">No matching transcripts found.</div>'; return; }
        filtered.forEach(fileName => {
            const card = document.createElement('div');
            card.className = 'transcript-card';
            card.onclick = () => loadTranscriptContent(fileName);
            const ext = fileName.split('.').pop().toUpperCase();
            card.innerHTML = `<div class="t-icon">📄</div><div class="t-info"><div class="t-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div><div class="t-meta">${ext} File</div></div>`;
            grid.appendChild(card);
        });
    }

    function loadTranscriptContent(fileName) { // Updated parameter handling if called directly
        // Handle case where called from onclick element
        if (typeof fileName === 'object' && fileName.getAttribute) {
             fileName = fileName.getAttribute('data-filename');
        }
        
        const modal = document.getElementById('text-modal');
        const textArea = document.getElementById('modal-text-content');
        const sidebarArea = document.getElementById('modal-sidebar-content');
        const titleArea = document.getElementById('modal-title');

        titleArea.innerText = `Transcript: ${fileName}`;

        // Get Raw Text
        let rawText = DATA.transcriptContents[fileName];
        if (!rawText) {
            textArea.innerText = `ERROR: Could not find embedded content for file: ${fileName}`;
            openTextModal();
            return;
        }

        // Escape HTML in raw text manually first
        let processedHtml = rawText.replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;")
                              .replace(/"/g, "&quot;")
                              .replace(/'/g, "&#039;");

        // Identify Participant ID ... (existing code) ...
        const pId = fileName.replace(/\.[^/.]+$/, "").toLowerCase();
        
        const relevantRecords = DATA.irrRecords.filter(r => {
            const recP = (r.p || "").toLowerCase().trim();
            if (!recP) return false;
            const safeRecP = recP.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(^|_|-|\\b)${safeRecP}($|_|-|\\b)`);
            return regex.test(pId);
        });

        // 1. Build Sidebar Data
        const uniqueCodes = {};
        relevantRecords.forEach(r => {
            if (!uniqueCodes[r.code]) {
                uniqueCodes[r.code] = { count: 0, coders: new Set() };
            }
            uniqueCodes[r.code].count++;
            // Find which coders were active
            DATA.coders.forEach(c => {
                if (r[c] === 1) uniqueCodes[r.code].coders.add(c);
            });
        });

        // Render Sidebar
        sidebarArea.innerHTML = '<h4 style="margin-top:0; border-bottom:1px solid var(--border); padding-bottom:10px;">Codes Found</h4>';
        if (Object.keys(uniqueCodes).length === 0) {
            sidebarArea.innerHTML += '<div style="padding:10px; opacity:0.7">No codes linked to this participant ID.</div>';
        } else {
            Object.keys(uniqueCodes).sort().forEach(code => {
                const info = uniqueCodes[code];
                const div = document.createElement('div');
                div.className = 'sidebar-code-item';
                
                // Create dots for coders
                let coderDots = '';
                info.coders.forEach(c => {
                    coderDots += `<span class="coder-dot" style="background-color:${getCoderColor(c)}" title="${c}"></span>`;
                });

                div.innerHTML = `
                    <div style="font-weight:600; margin-bottom:4px;">${code}</div>
                    <div style="font-size:0.8em; opacity:0.8;">
                        ${coderDots}
                        <span style="float:right;">${info.count} refs</span>
                    </div>
                `;
                div.onclick = () => highlightSpecificCode(code);
                sidebarArea.appendChild(div);
            });
        }

        // 2. Highlight Text
        const sortedRecords = [...relevantRecords].sort((a, b) => b.text.length - a.text.length);
        const uniqueSegments = [...new Set(sortedRecords.map(r => r.text))];

        uniqueSegments.forEach(segmentText => {
            if (!segmentText || segmentText.length < 2) return;

            const matchRecs = relevantRecords.filter(r => r.text === segmentText);
            let activeCoders = new Set();
            matchRecs.forEach(r => {
                DATA.coders.forEach(c => { if(r[c] === 1) activeCoders.add(c); });
            });
            
            const coderArray = Array.from(activeCoders);
            const mainColor = coderArray.length > 0 ? getCoderColor(coderArray[0]) : 'var(--primary)';
            const tooltip = `Codes: ${[...new Set(matchRecs.map(r=>r.code))].join(', ')}\nCoders: ${coderArray.join(', ')}`;
            const dataCodes = [...new Set(matchRecs.map(r=>r.code))].join('|');

            const replacement = `<span class="highlight-span" style="border-color:${mainColor}" title="${tooltip}" data-codes="${dataCodes}">$&</span>`;
            
            try {
               const trimmed = segmentText.trim();

               // Split into words to handle whitespace robustly (matching tabs, newlines, nbsp)
               const tokens = trimmed.split(/[\s\u00A0]+/);

               const escapedTokens = tokens.map(t => {
                   // Use '\\$&' (2 backslashes) in Python raw string.
                   // Python writes \\$& to file. JS sees literal backslash + $&.
                   // JS Replace produces: Literal Backslash + Matched Char (e.g. "\[").
                   // This correctly escapes the character for the Regex engine.
                   let safe = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                   
                   // Handle HTML Entities
                   safe = safe.replace(/&/g, "&amp;")
                              .replace(/</g, "&lt;")
                              .replace(/>/g, "&gt;");

                   // Handle Quotes (Smart vs Straight)
                   safe = safe.replace(/['’‘]/g, "(?:&#039;|'|’|‘)");
                   safe = safe.replace(/["“”]/g, "(?:&quot;|\"|“|”)");

                   // Handle Punctuation
                   safe = safe.replace(/\\\.\\\.\\\./g, "(?:\\.\\.\\.|…)");
                   safe = safe.replace(/-/g, "(?:-|–|—)");
                   
                   return safe;
               });

               // Join with robust whitespace regex that tolerates HTML tags in between words
               const spaceRegex = '(?:<[^>]+>)*[\\s\\u00A0]+(?:<[^>]+>)*';
               let pattern = escapedTokens.join(spaceRegex);

               const re = new RegExp(pattern, 'gi');
               processedHtml = processedHtml.replace(re, replacement);
            } catch(e) { console.log("Regex error", e); }
        });

        textArea.innerHTML = processedHtml;
        openTextModal();
    }

    function highlightSpecificCode(code) {
        // Remove active class from sidebar items
        document.querySelectorAll('.sidebar-code-item').forEach(el => el.classList.remove('active'));
        // Add to clicked
        event.currentTarget.classList.add('active');

        const spans = document.querySelectorAll('.highlight-span');
        let firstFound = null;

        spans.forEach(span => {
            const spanCodes = (span.getAttribute('data-codes') || "").split('|');
            if (spanCodes.includes(code)) {
                span.classList.add('highlight-active');
                if(!firstFound) firstFound = span;
            } else {
                span.classList.remove('highlight-active');
            }
        });

        if (firstFound) {
            firstFound.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }
    
    let codebookState = [];
    let codebookSort = { col: null, asc: true };

    function renderCodebookTable() {
        const root = document.getElementById('codebook-table-root');
        const columns = DATA.codebook.columns;
        
        // Initialize state on first run
        if (codebookState.length === 0 && DATA.codebook.rows.length > 0) {
            codebookState = JSON.parse(JSON.stringify(DATA.codebook.rows));
            codebookState.forEach((r, i) => r._ui_id = i);
        }
        
        if (columns.length === 0) {
            root.innerHTML = '<p>No codebook definition found or file is empty.</p>';
            return;
        }

        const searchTerm = document.getElementById('codebook-search').value.toLowerCase();

        let displayRows = codebookState.filter(row => {
            if (!searchTerm) return true;
            return Object.values(row).some(val => 
                String(val).toLowerCase().includes(searchTerm)
            );
        });

        // Sorting logic (preserved)
        if (codebookSort.col) {
            displayRows.sort((a, b) => {
                let valA = a[codebookSort.col] || "";
                let valB = b[codebookSort.col] || "";
                const numA = parseFloat(valA);
                const numB = parseFloat(valB);
                if (!isNaN(numA) && !isNaN(numB)) { valA = numA; valB = numB; } 
                else { valA = String(valA).toLowerCase(); valB = String(valB).toLowerCase(); }

                if (valA < valB) return codebookSort.asc ? -1 : 1;
                if (valA > valB) return codebookSort.asc ? 1 : -1;
                return 0;
            });
        }

        // Attempt to identify a category column for coloring
        const catCol = columns.find(c => c.toLowerCase().includes('cat') || c.toLowerCase().includes('group'));

        // Define column width logic
        const getColClass = (colName) => {
            const lower = colName.toLowerCase();
            if (lower.includes('id') && !lower.includes('description')) return 'col-narrow';
            if (lower.includes('description') || lower === 'includes' || lower === 'excludes') return 'col-wide';
            return 'col-normal';
        };

        let html = '<table class="def-table"><thead><tr>';
        html += '<th class="action-cell">Actions</th>'; 
        columns.forEach(col => {
            const arrow = codebookSort.col === col ? (codebookSort.asc ? ' ▲' : ' ▼') : '';
            const colClass = getColClass(col);
            html += `<th class="${colClass}" onclick="sortCodebook('${col}')">${col}${arrow}</th>`;
        });
        html += '</tr></thead><tbody>';

        displayRows.forEach(row => {
            // Determine row color based on category column
            let rowStyle = '';
            let cellStyle = '';
            if (catCol && row[catCol]) {
                const baseColor = getCoderColor(String(row[catCol])); // baseColor is now HSL
                
                // NEW LOGIC: Extract HUE from the base color string (e.g., '120')
                const hueMatch = baseColor.match(/hsl\((\d+)/);
                const hue = hueMatch ? hueMatch[1] : 0;
                
                // Create a very faint background using HSLA (lightness reduced to 20%
                // and opacity set to 0.5) for a readable background color.
                const bg = `hsla(${hue}, 70%, 20%, 0.5)`; 
                
                rowStyle = `background-color: ${bg};`;
                // Stronger border uses the vivid HSL color
                rowStyle += `border-left: 5px solid ${baseColor};`;
            }

            html += `<tr style="${rowStyle}">`;
            html += `<td class="action-cell"><button class="btn-danger btn-sm" onclick="deleteCodebookRow(${row._ui_id})">✕</button></td>`;
            columns.forEach(col => {
                const val = row[col] !== undefined ? row[col] : "";
                html += `<td><textarea onchange="updateCodebookCell(${row._ui_id}, '${col}', this.value)">${escapeHtml(String(val))}</textarea></td>`;
            });
            html += `</tr>`;
        });

        html += '</tbody></table>';
        root.innerHTML = html;
    }

    function sortCodebook(col) {
        if (codebookSort.col === col) {
            codebookSort.asc = !codebookSort.asc;
        } else {
            codebookSort.col = col;
            codebookSort.asc = true;
        }
        renderCodebookTable();
    }

    function updateCodebookCell(id, col, value) {
        const row = codebookState.find(r => r._ui_id === id);
        if (row) {
            row[col] = value;
        }
    }

    // Visual confirmation of save
    function saveCurrentEdit() {
        const btn = document.getElementById('btn-save-edit');
        
        // In reality, data is already in 'codebookState', so this is just UX
        // Display a more informative message about in-memory-only save
        btn.innerText = "✓ Saved (In-Memory Only)!";
        btn.style.backgroundColor = "var(--success)";
        
        setTimeout(() => {
            btn.innerText = "Save current edit";
            btn.style.backgroundColor = ""; // revert to CSS class
        }, 3000); // Keep the message visible for longer

        // Provide a temporary alert/tooltip message near the button or use the existing informational paragraph.
        const infoParagraph = document.querySelector('#view-codebook p');
        if (infoParagraph) {
            infoParagraph.innerHTML = `
                <strong style="color:var(--success);">Changes saved to browser memory!</strong> To keep these edits, you must click 
                <strong>'Download CSV'</strong> or <strong>'Download Excel'</strong> before leaving or refreshing the page.
            `;
             setTimeout(() => {
                infoParagraph.innerHTML = `Note: Click 'Save current edit' to confirm changes in memory before switching tabs. Use Download buttons to export files.`;
            }, 5000);
        }
    }

    function deleteCodebookRow(id) {
        if (confirm("Are you sure you want to delete this row?")) {
            codebookState = codebookState.filter(r => r._ui_id !== id);
            renderCodebookTable();
        }
    }

    function addCodebookRow() {
        const newRow = { _ui_id: Date.now() }; // simple unique id
        DATA.codebook.columns.forEach(col => newRow[col] = "");
        // Insert at top
        codebookState.unshift(newRow);
        renderCodebookTable();
    }

    function getCleanData() {
        return codebookState.map(row => {
            const { _ui_id, ...rest } = row;
            return rest;
        });
    }

    async function exportCodebookXLSX() {
        const cleanData = getCleanData();
        if (cleanData.length === 0) return;
        
        const columns = DATA.codebook.columns;
        const catCol = columns.find(c => c.toLowerCase().includes('cat') || c.toLowerCase().includes('group'));
        
        // Create workbook and worksheet
        const workbook = new ExcelJS.Workbook();
        const worksheet = workbook.addWorksheet('Codebook');

        // Add headers
        const headerRow = worksheet.addRow(columns);
        headerRow.font = { bold: true };
        
        // Add Data with styling
        cleanData.forEach(dataRow => {
            const rowValues = columns.map(col => dataRow[col] || "");
            const addedRow = worksheet.addRow(rowValues);
            
            // Apply color if category exists
            if (catCol && dataRow[catCol]) {
                // Recalculate color as Hex for Excel because getCoderColor returns HSL
                const name = String(dataRow[catCol]);
                let index = DATA.coders.indexOf(name);
                if (index === -1) {
                    let hash = 0;
                    for (let i = 0; i < name.length; i++) {
                        hash = name.charCodeAt(i) + ((hash << 5) - hash);
                    }
                    index = Math.abs(hash);
                }
                const hue = (index * 137.508) % 360;
                
                // HSL to Hex conversion (using S=0.75, L=0.45 to match getCoderColor)
                const s = 0.75, l = 0.45;
                const k = n => (n + hue / 30) % 12;
                const a = s * Math.min(l, 1 - l);
                const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
                const toHex = x => Math.round(x * 255).toString(16).padStart(2, '0');
                const hexColor = `${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`;

                // Use a very light shade of the color for the fill by appending 70% opacity in AARRGGBB
                const lightFillColor = '33' + hexColor; 
                
                // Apply to each cell in row
                addedRow.eachCell({ includeEmpty: true }, (cell, colIndex) => {
                    cell.fill = {
                        type: 'pattern',
                        pattern: 'solid',
                        fgColor: { argb: lightFillColor }, 
                    };
                    
                    // Add border for clarity (optional but looks better)
                    const baseBorder = {style:'thin', color: {argb:'FF888888'}};
                    const leftBorder = colIndex === 1 
                        ? {style:'thick', color: {argb: 'FF' + hexColor}} 
                        : baseBorder;
                        
                    cell.border = {
                        top: baseBorder,
                        left: leftBorder,
                        bottom: baseBorder,
                        right: baseBorder
                    };
                });
            }
            
            // Set text wrapping for description columns
            addedRow.eachCell((cell, colNumber) => {
                const colName = columns[colNumber - 1].toLowerCase();
                 if (colName.includes('description') || colName === 'includes' || colName === 'excludes') {
                     cell.alignment = { wrapText: true, vertical: 'top' };
                 } else {
                     cell.alignment = { vertical: 'top' };
                 }
            });
        });

        // Adjust column widths based on content type
        worksheet.columns = columns.map(col => {
            const lower = col.toLowerCase();
            let width = 20;
            if (lower.includes('id') && !lower.includes('description')) width = 12;
            if (lower.includes('description') || lower === 'includes' || lower === 'excludes') width = 50;
            return { width: width };
        });

        // Write file
        const buffer = await workbook.xlsx.writeBuffer();
        const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'updated_codebook.xlsx';
        a.click();
        window.URL.revokeObjectURL(url);
    }
    
    function exportCodebookCSV() {
        const cleanData = getCleanData();
        if (cleanData.length === 0) return;
        
        const headers = Object.keys(cleanData[0]);
        const csvRows = [headers.join(',')];

        cleanData.forEach(row => {
            const values = headers.map(header => {
                const escaped = ('' + (row[header] || '')).replace(/"/g, '""');
                return `"${escaped}"`;
            });
            csvRows.push(values.join(','));
        });

        const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.setAttribute('hidden', '');
        a.setAttribute('href', url);
        a.setAttribute('download', 'updated_codebook.csv');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    function renderFAQ() {
        const root = document.getElementById('faq-list');
        const searchTerm = document.getElementById('faq-search').value.toLowerCase();
        root.innerHTML = '';

        DATA.faqData.forEach(item => {
            const q = item.q;
            const a = item.a;
            
            // Simple search logic
            if (searchTerm && !q.toLowerCase().includes(searchTerm) && !a.toLowerCase().includes(searchTerm)) {
                return;
            }

            const el = document.createElement('div');
            el.className = 'faq-item';
            
            el.innerHTML = `
                <div class="faq-question" onclick="toggleFAQ(this)">${q}</div>
                <div class="faq-answer">${a}</div>
            `;
            root.appendChild(el);
        });

        if (root.children.length === 0) {
            root.innerHTML = '<div style="text-align:center; padding:20px; opacity:0.6;">No questions found matching your search.</div>';
        }
    }

    function toggleFAQ(headerElement) {
        const item = headerElement.parentElement;
        item.classList.toggle('open');
    }

    function filterFAQ() {
        renderFAQ();
    }

</script>
</body>
</html>
"""

    for key, value in context.items():
        placeholder = f"{{{key}}}"
        html_template = html_template.replace(placeholder, str(value))
    return html_template

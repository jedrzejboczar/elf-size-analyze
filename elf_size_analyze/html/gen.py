"""
Generator functions for HTML output
"""

import os
import html

THIS_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
DEFAULT_CSS = os.path.join(THIS_DIR, 'styles.css')
JAVASCRIPT = os.path.join(THIS_DIR, 'index.js')

def generate_html_output(node_dict, title, custom_css=None):
    table_content = ""

    custom_css = custom_css or DEFAULT_CSS
    with open(custom_css, encoding='utf-8') as f:
        css_styles = f.read()

    with open(JAVASCRIPT, encoding='utf-8') as f:
        javascript = f.read()

    def _print_children(node, level=0):
        nonlocal table_content
        for x, y in node.items():
            table_content += f"""
            <tr class="collapsible level-{level}">
                <td style='padding-left:{10*level}px;word-break:break-all;word-wrap:break-word'>{html.escape(x)}</td>
                <td width='200px' align='right'>{y['cumulative_size']}</td>
            </tr>
    """

            if "children" in y:
                _print_children(y["children"], level + 1)

    _print_children(node_dict)

    overall_size = 0
    for x,y in node_dict.items():
        overall_size = overall_size + y["cumulative_size"]

    html_output = f"""
<!DOCTYPE html>
<html lang="en">
    <head>
        <title>{html.escape(title)}</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>{css_styles}</style>
        <script>{javascript}</script>
    </head>
    <body>
        <h3>{html.escape(title)}</h3>
        <div class="collapse-buttons">
            <span>Collapse</span>
            <button class="all">All</button>
            <button class="none">None</button>
            <button class="less">Less</button>
            <button class="more">More</button>
            <span>or click on rows</span>
        </div>
        <table>{table_content}
            <tr>
                <td align="right"><b>Overall size in bytes</b></td>
                <td align="right">{overall_size}</td>
            </tr>
        </table>
    </body>
</html>
"""

    return html_output

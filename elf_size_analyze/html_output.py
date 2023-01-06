"""
Generator functions for HTML output
"""


def generate_html_output(node_dict, title, custom_css = None):
    table_content = ""

    _css_style = """
                tr:nth-child(even) {
                    background-color: #efefef;
                }
                tr:nth-child(odd) {
                    background-color: #e0e0e0;
                }
                table {
                    border-spacing: 0px;
                    table-layout:fixed;
                    width: 100%;
                }
                h3 {
                    font-family: "Verdana";
                    font-size: 14pt;
                }
                td {
                    font-family: "Verdana";
                    font-size: 10pt;
                }
                tr:hover {
                    background: #adf0c2 !important;
                }
    """

    def _print_children(node, level=0):
        nonlocal table_content
        for x, y in node.items():
            table_content += f"""
            <tr>
                <td style='padding-left:{10*level}px;word-break:break-all;word-wrap:break-word'>{x}</td>
                <td width='200px' align='right'>{y['cumulative_size']}</td>
            </tr>
    """
            
            if "children" in y:
                _print_children(y["children"], level + 1)
        
    _print_children(node_dict)
    
    overall_size = 0
    for x,y in node_dict.items():
        overall_size = overall_size + y["cumulative_size"]

    if custom_css:
        with open(custom_css) as style_file:
            _css_style = style_file.read()

    html_output = f"""<!DOCTYPE html>
<html>
    <head>
        <title>{title}</title>
        <style>{_css_style}
        </style>
    </head>
    <body>
        <h3>{title}</h3>
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
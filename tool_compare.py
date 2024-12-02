#!/tool/pandora64/hdk-2021/1.1/bin/python3  
  
"""  
Tips:
    use the extensions: SingleFile to capture the html files from the target url 

Usage: 
    ./tool_compare.py --copy_html   
"""  
from bs4 import BeautifulSoup    
import argparse  
from datetime import datetime
import re  
import pdb  
import os  
import shutil
import subprocess
import sys
import pdb
import requests

#############################################################################################################  
# Globals  
CONFLUENCE_URL = 'https://confluence.amd.com'  
ca_cert_path = '/etc/ssl/certs/ca-bundle.crt'  
  
headers = {  
    "Content-Type": "application/json",  
    "Accept": "application/json",  
}  
#############################################################################################################  
# Parse Command Line  
def parse_command_line():  
    parser = argparse.ArgumentParser(description='Extract data from HTML table')  
    parser.add_argument('--output_dir', '-o', default='tool_compare', help='Output directory for generated HTML files')  
    parser.add_argument('--copy_html', action='store_true', help='Copy HTML to webpage /proj/gpg_asdc_webdata/gfxweb/tool_compare/')  
    parser.add_argument('--debug', action='store_true', help='Debug mode to print necessary info')  
    args = parser.parse_args()  
  
    return args  
  
#############################################################################################################  
# get html content from the webpage
def get_html_context_from_webpage(confluence_username, confluence_password, page_id):  
    api_url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=body.view"

    response = requests.get(api_url, headers=headers,   
                            auth=(f"{confluence_username}", f"{confluence_password}"),  
                            verify=f"{ca_cert_path}")  
  
    if response.status_code != 200:  
        print(f"Error getting page: {response.status_code}")
        print("Response content: ", response.text) 
        sys.exit(1) 
  
    page_data = response.json()  
    html_content = page_data['body']['view']['value']  

    return html_content

#############################################################################################################
# fix html
def fix_html(html_content):
    return html_content.replace('</td>', '').replace('<td', '</td><td')

#############################################################################################################
# parse html for tool info
def get_soc_tool_info_from_webpage(html_content):
    tool_info = {}  
    fixed_html = fix_html(html_content)

    soup = BeautifulSoup(fixed_html, 'html.parser')  
    tables = soup.find_all('table')  
  
    for table in tables:  
        if 'Shared Component' not in table.get_text(): 
            
            rows = table.find_all('tr')  

            for row in rows:  
                cols = row.find_all('td')  
  
                if len(cols) >= 4 and cols[1].get_text(strip=True) != 'Tool Name' and cols[1].get_text(strip=True) != 'Tools/Components Name':  
                    tool_name = cols[1].get_text(strip=True) 

                    # HACK for SOUNDWAVE LSD
                    if os.environ['DJ_CONTEXT'] == 'soundwave':  
                        tool_version = cols[4].get_text(strip=True)  
                    else:
                        tool_version = cols[3].get_text(strip=True) 
  
                    if tool_name not in tool_info:  
                        tool_info[tool_name] = []  
  
                    if tool_version not in tool_info[tool_name]:  
                        tool_info[tool_name].append(tool_version)  
  
    return tool_info


#############################################################################################################
# get timestamp from the html
def get_soc_timestamp(confluence_username, confluence_password, page_id):

    api_url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}?expand=version.when"

    response = requests.get(api_url, headers=headers,   
                            auth=(f"{confluence_username}", f"{confluence_password}"),  
                            verify=f"{ca_cert_path}")  
  
    if response.status_code != 200:  
        raise f"Error getting page: {response.status_code}" 
        sys.exit(1) 
  
    page_data = response.json() 

    datetime_str = page_data['version']['when'] 
    
    date_obj = datetime.fromisoformat(datetime_str[:-6])    
    timestamp = date_obj.strftime("%Y-%m-%d")  

    return timestamp

#############################################################################################################
# get codeline and changelist from the ws
def get_gfxip_codeline():
    try: 
        with open(f"{os.getenv('STEM')}/configuration_id", 'r') as file:
            lines = file.readline().strip()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

    return lines 

#############################################################################################################  
# get loaded modules by `module list` 
def get_loaded_modules():  
    tclsh_path = os.getenv('TCLSH')  
    modulecmd_path = os.getenv('MODULESHOME') + '/modulecmd.tcl'
    
    if not tclsh_path or not modulecmd_path:  
        print("Error: TCLSH or MODULESHOME environment variable is not set.")  
        return []

    try:  
        command = f'{tclsh_path} {modulecmd_path} tcsh list'  
          
        result = subprocess.run(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)  
          
        if result.returncode != 0:  
            print(f"Error: {result.stderr}")  
            return []  

        output_lines = result.stdout.splitlines()  + result.stderr.splitlines()
          
        processed_lines = [line for line in output_lines if line.strip() and not line.startswith("Currently Loaded Modulefiles:")]  
        
        return processed_lines  
      
    except Exception as e:  
        print(f"An error occurred: {e}")  
        return []  
 
#############################################################################################################  
# get gfxip tools info
def get_gfxip_tool_info(loaded_modules): 
    tool_info = {}  
      
    # regular expression to match tool names and versions  
    # \w+[-\w]*: match one or more word characters followed by zero or more hyphens and word characters   
    # for example : 'tool-name' or 'toolname'  
    # [\w.-]+: match one or more word characters, hyphens, or periods  
    # for example : '8.6.6' or '1.9.3-p0'     
    pattern = re.compile(r'([\w.-]+)/([\w.-]+)')  
      
    # Excluded values  
    excluded_values = {'proj', 'verif_release_ro', 'ip_release_ro', 'home'}  
  
    # add environment variables to excluded values  
    stem_values = os.getenv('STEM')  
    if stem_values:  
        excluded_values.update(stem_values.split('/'))  
    
    def extract_tool_version(line):  
        matches = pattern.findall(line)  
        for match in matches:  
            if match[1] not in excluded_values and match[0] not in excluded_values:  
                tool = match[0]  
                version = match[1]  
                  
                if tool not in tool_info:    
                    tool_info[tool] = []   
  
                if version not in tool_info[tool]:   
                    tool_info[tool].append(version) 
                return     
  
            # Handle the remain part of the line  
            line = line.replace(f'{match[0]}/{match[1]}', '')  
            extract_tool_version(line)  
    
    # parse the modules 
    for line in loaded_modules: 
        if stem_values in line:  
            continue
        extract_tool_version(line)  
  
    return tool_info       

#############################################################################################################
# Write styles to the html file
def write_styles(file):  
    styles = """  
    <style>  
        body {  
            font-family: Arial, sans-serif;  
            text-align: center;  
            background-color: #f4f4f4;  
            margin: 0;  
            padding: 0;  
        }  
        header {  
            background-color: #333;  
            color: white;  
            padding: 10px 0;  
            margin-bottom: 20px;  
            display: flex;  
            justify-content: space-between;  
            align-items: center;  
        }  
        header a {  
            margin: 0 15px;  
            text-decoration: none;  
            color: white;  
            font-weight: bold;  
        }  
        .card {  
            background-color: white;  
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);  
            padding: 20px;  
            margin: 20px;  
            border-radius: 8px;  
            text-align: left;  
        }  
        .card h2 {  
            color: #333;  
        }  
        table {  
            font-family: Arial, sans-serif;  
            border-collapse: collapse;  
            width: 80%;  
            margin: 20px auto;  
            background-color: white;  
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);  
        }  
        td, th {  
            border: 1px solid #dddddd;  
            text-align: left;  
            padding: 8px;  
        }  
        tr:nth-child(even) {  
            background-color: #f9f9f9;  
        }  
        .same { background-color: lightgreen; }  
        .different { background-color: red; color: white; }  
        .missing-soc { background-color: yellow; }  
        .missing-gfxip { background-color: orange; }  
        h1, h2 {  
            color: #333;  
        }  
        .info {  
            background-color: #e7f3fe;  
            border-left: 6px solid #2196F3;  
            margin: 20px;  
            text-align: left;  
            padding: 10px;  
            padding-left: 20px;  
        } 
        .timestamp-container {
            font-size: 0.9em;
            color: #666;
            margin-top: -10px;
        } 
        .timestamp  {
            margin: 5px 0;
        }
    </style>  
    """  
    file.write(styles)  

#############################################################################################################  
# Generate HTML header  
def generate_html_header(file, title):  
    file.write('<html>\n<head>\n')  
    file.write(f'<title>{title}</title>\n')  
    write_styles(file)  
    file.write('</head>\n<body>\n<header>\n')  
    file.write('<div>\n<a href="index.html">Back to Main</a>\n<a href="same_tool.html">Same Tool Versions</a>\n<a href="different_tool.html">Different Tool Versions</a>\n<a href="missing_tool.html">Missing Tool Versions</a>\n</div>\n')  
    file.write('<div>\n<a href="soc_tool_info.html">SoC Tool Info</a>\n<a href="gfxip_tool_info.html">GFXIP Tool Info</a>\n</div>\n</header>\n')  
    file.write(f'<h1>{title}</h1>\n')  
    file.write('<div class="timestamp-container">\n')
    file.write(f'<div class="timestamp">Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>\n')  
    file.write(f'<div class="timestamp">Updated by: {os.getenv("USER")}</div>\n') 
    file.write('</div>\n') 
    file.write(f'<div class="info">\n<p><strong>SoC Report (<a href="{confluence_url}">Confluence Page</a>) Provided on:</strong> {soc_timestamp}</p>\n<p><strong>GFXIP Codeline Information:</strong> {gfxip_codeline}</p>\n</div>\n') 

#############################################################################################################  
# Generate HTML table header  
def generate_html_table_header(file, type="", is_index=False):  
    file.write('<table>\n')      
    file.write('  <tr>\n')  
    if not is_index:    
        file.write('    <th>No.</th>\n')      
    file.write('    <th>Tool</th>\n')      
    if type == "" or type == "comparison":  
        file.write('    <th>SoC Version</th>\n')      
        file.write('    <th>GFXIP Version</th>\n')      
    elif type == "soc_tool_info":  
        file.write('    <th>SoC Version</th>\n')      
    elif type == "gfxip_tool_info":  
        file.write('    <th>GFXIP Version</th>\n')      
    file.write('  </tr>\n')   

#############################################################################################################  
# Generate HTML table row for tool info  
def generate_html_tool_info_row(file, tool_info):  
    count = 1  
    for tool in sorted(tool_info.keys()):  
        versions = tool_info[tool]  
        versions_str = (", ").join(versions)  
        file.write(f'  <tr>\n')  
        file.write(f'    <td>{count}</td>\n')  
        file.write(f'    <td>{tool}</td>\n')  
        file.write(f'    <td>{versions_str}</td>\n')  
        file.write(f'  </tr>\n')  
        count += 1 
  
#############################################################################################################  
# Generate HTML table row for comparison  
def generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, filter_type, is_index=False):  
    count = 1  
  
    if filter_type == "same":  
        for tool in sorted(soc_tool_info.keys()):  
            soc_versions = soc_tool_info[tool]  
            soc_versions_str = (", ").join(soc_versions)  
            gfxip_versions_str = (", ").join(gfxip_tool_info.get(tool, []))  
            if tool in gfxip_tool_info:  
                if soc_versions == gfxip_tool_info[tool]:  
                    file.write(f'  <tr>\n')  
                    if not is_index:
                        file.write(f'    <td>{count}</td>\n')  
                    file.write(f'    <td>{tool}</td>\n')  
                    file.write(f'    <td class="same">{soc_versions_str}</td>\n')  
                    file.write(f'    <td class="same">{gfxip_versions_str}</td>\n')  
                    file.write(f'  </tr>\n')  
                    count += 1  
  
    elif filter_type == "different":  
        for tool in sorted(soc_tool_info.keys()):    
            soc_versions = soc_tool_info[tool]  
            soc_versions_str = (", ").join(soc_versions)    
            gfxip_versions_str = (", ").join(gfxip_tool_info.get(tool, []))    
            if tool in gfxip_tool_info:    
                if soc_versions != gfxip_tool_info[tool]:    
                    file.write(f'  <tr>\n')  
                    if not is_index:  
                        file.write(f'    <td>{count}</td>\n')    
                    file.write(f'    <td>{tool}</td>\n')    
                    file.write(f'    <td class="different">{soc_versions_str}</td>\n')    
                    file.write(f'    <td class="different">{gfxip_versions_str}</td>\n')    
                    file.write(f'  </tr>\n')    
                    count += 1  
  
    elif filter_type == "missing":  
        for tool in sorted(soc_tool_info.keys()):    
            soc_versions = soc_tool_info[tool]  
            soc_versions_str = (", ").join(soc_versions)    
            if tool not in gfxip_tool_info:    
                file.write(f'  <tr>\n')  
                if not is_index:  
                    file.write(f'    <td>{count}</td>\n')    
                file.write(f'    <td>{tool}</td>\n')    
                file.write(f'    <td class="missing-soc">{soc_versions_str}</td>\n')    
                file.write(f'    <td class="missing-soc">Missing</td>\n')    
                file.write(f'  </tr>\n')    
                count += 1  
  
        for tool in sorted(gfxip_tool_info.keys()):  
            if tool not in soc_tool_info:  
                gfxip_versions = gfxip_tool_info[tool]  
                gfxip_versions_str = (", ").join(gfxip_versions)  
                file.write(f'  <tr>\n')  
                if not is_index:
                    file.write(f'    <td>{count}</td>\n')  
                file.write(f'    <td>{tool}</td>\n')  
                file.write(f'    <td class="missing-gfxip">Missing</td>\n')  
                file.write(f'    <td class="missing-gfxip">{gfxip_versions_str}</td>\n')  
                file.write(f'  </tr>\n')  
                count += 1  

#############################################################################################################  
# Generate HTML footer  
def generate_html_footer(file):  
    file.write('</table>\n')    
    file.write('</body>\n')    
    file.write('</html>\n')  
  
#############################################################################################################  
# Generate the html, the display green for the same version and red for the different version and yellow for missing  
def generate_html(soc_tool_info, gfxip_tool_info, output_dir):  
    os.makedirs(output_dir, exist_ok=True)  
  
    with open(os.path.join(output_dir, 'index.html'), 'w') as file:  
        generate_html_header(file, f"{os.getenv('DJ_CONTEXT').upper()} - Tool Comparison Report")  
        generate_html_table_header(file, 'comparison', is_index=True)
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "different", is_index=True)  
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "same", is_index=True)  
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "missing", is_index=True)  
        generate_html_footer(file)  
  
    with open(os.path.join(output_dir, 'same_tool.html'), 'w') as file:  
        generate_html_header(file, "Same Tool Versions")  
        generate_html_table_header(file, "comparison")  
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "same")  
        generate_html_footer(file)  
  
    with open(os.path.join(output_dir, 'different_tool.html'), 'w') as file:  
        generate_html_header(file, "Different Tool Versions")  
        generate_html_table_header(file, "comparison")  
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "different")  
        generate_html_footer(file)  
  
    with open(os.path.join(output_dir, 'missing_tool.html'), 'w') as file:  
        generate_html_header(file, "Missing Tool Versions")  
        generate_html_table_header(file, "comparison")  
        generate_html_comparison_row(file, soc_tool_info, gfxip_tool_info, "missing")  
        generate_html_footer(file)  
  
    with open(os.path.join(output_dir, 'soc_tool_info.html'), 'w') as file:  
        generate_html_header(file, "SoC Tool Info")  
        generate_html_table_header(file, "soc_tool_info")  
        generate_html_tool_info_row(file, soc_tool_info)  
        generate_html_footer(file)  
  
    with open(os.path.join(output_dir, 'gfxip_tool_info.html'), 'w') as file:  
        generate_html_header(file, "GFXIP Tool Info")  
        generate_html_table_header(file, "gfxip_tool_info")  
        generate_html_tool_info_row(file, gfxip_tool_info)  
        generate_html_footer(file)  

#############################################################################################################  
# Copy generated files to the specified directory  
def copy_generated_files(output_dir, copy_to):  
    if not os.path.exists(copy_to):  
        os.makedirs(copy_to) 
        os.chmod(copy_to, 0o775) 
    for filename in os.listdir(output_dir):  
        full_file_name = os.path.join(output_dir, filename)  
        if os.path.isfile(full_file_name):  
            shutil.copy(full_file_name, copy_to)  


#############################################################################################################  
# Extract page id
def extract_page_id(url):  
    match = re.search(r'pageId=(\d+)', url)  
    if match:
        return match.group(1)
    else:
        print("Invalid URL: Could not extract pageId. Please select the page version from Page History to obtain a URL with a pageId.")
        sys.exit(1)

#############################################################################################################  
# Main function   
def main():  
    args = parse_command_line()  
 
    global soc_timestamp, gfxip_codeline, confluence_url

    confluence_username = input("Enter Confluence Username:")  
    confluence_password = input("Enter Confluence Password:")
    confluence_url = input("Enter Confluence Url:")

    page_id = extract_page_id(confluence_url)

    html_content = get_html_context_from_webpage(confluence_username, confluence_password, page_id)
    # get the tools info of SoC and IP 
    soc_tool_info = get_soc_tool_info_from_webpage(html_content)  
    gfxip_tool_info = get_gfxip_tool_info(get_loaded_modules())  
      
    # get the timestamp of the SoC html file and the codeline of the GFX
    soc_timestamp = get_soc_timestamp(confluence_username, confluence_password, page_id)
    gfxip_codeline = get_gfxip_codeline()

    # generate the html files
    generate_html(soc_tool_info, gfxip_tool_info, args.output_dir)  

    # copy the generated files to the webpage
    if args.copy_html:
        copy_generated_files(args.output_dir, f"/proj/gpg_asdc_webdata/gfxweb/tool_compare/{os.getenv('DJ_CONTEXT')}")

if __name__ == '__main__':  
    main()


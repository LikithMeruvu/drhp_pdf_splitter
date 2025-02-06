# import streamlit as st
# import requests
# from bs4 import BeautifulSoup
# import io
# import fitz  # PyMuPDF
# import re
# import zipfile
# import pandas as pd
# import os

# ##########################################
# # Optional: Inject a little custom style #
# ##########################################

# st.set_page_config(page_title="PDF Splitter", layout="wide")

# # Some small spacing tweaks, e.g. for checkboxes under expanders
# CUSTOM_CSS = """
# <style>
#     /* Slightly bigger font for the checkboxes */
#     .streamlit-expanderHeader > div > label {
#         font-size: 1.1rem !important;
#         font-weight: 600 !important;
#     }
#     /* Indent sub-section checkboxes */
#     .subsection-checkbox {
#         margin-left: 2em !important; /* adjust indentation here */
#         font-size: 1rem !important;
#     }
# </style>
# """
# st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ######################
# # Utility Functions  #
# ######################

# def fetch_pdf_from_webpage(url: str) -> io.BytesIO:
#     """
#     Given a URL that may embed a PDF link in <iframe>, attempt to extract 
#     the actual PDF URL and return the PDF content as BytesIO.
#     Raises ValueError if no PDF found.
#     """
#     resp = requests.get(url)
#     if resp.status_code != 200:
#         raise ValueError(f"Failed to retrieve the webpage: {url}")

#     soup = BeautifulSoup(resp.content, "html.parser")
#     iframe = soup.find("iframe")
#     if iframe and iframe.get("src") and "file=" in iframe["src"]:
#         # The PDF link is something like src="...&file=<pdf_link>"
#         interimurl = iframe["src"]
#         pdf_url = interimurl.split("file=")[1]
#     elif iframe and iframe.get("src"):
#         # Possibly a direct link in src if it ends with .pdf
#         pdf_url = iframe["src"]
#     else:
#         # fallback: maybe the given URL itself is the PDF
#         pdf_url = url

#     pdf_url = pdf_url.strip()
#     if not pdf_url.lower().endswith(".pdf"):
#         raise ValueError("URL does not point to a valid PDF file or embedded PDF iframe.")

#     # Now fetch the actual PDF bytes
#     pdf_resp = requests.get(pdf_url)
#     if pdf_resp.status_code != 200:
#         raise ValueError(f"Failed to download PDF from {pdf_url}")

#     return io.BytesIO(pdf_resp.content)


# def extract_table_of_contents(pdf_path: str):
#     """
#     Extracts the PDF's Table of Contents using PyMuPDF.
#     Returns a DataFrame with section/subsection entries or None if no TOC found.
#     """
#     try: 
#         doc = fitz.open(pdf_path)
#     except Exception as e:
#         st.error(f"Error opening PDF: {e}")
#         return None
    
#     # Step 1: Try to locate a "Contents"/"TABLE OF CONTENTS" page within the first ~6 pages
#     toc_start_page = None
#     for page_num in range(min(6, doc.page_count)):
#         try:
#             page = doc.load_page(page_num)
#             text = page.get_text("text")
#             if "Contents" in text or "TABLE OF CONTENTS" in text:
#                 toc_start_page = page_num
#                 break
#         except:
#             continue

#     if toc_start_page is None:
#         doc.close()
#         return None  # Could not find a suitable TOC page

#     # Step 2: Extract data from this page onward until we no longer see TOC patterns
#     toc_data = []
#     page_num = toc_start_page

#     while page_num < doc.page_count:
#         try:
#             page = doc.load_page(page_num)
#             links = [l for l in page.get_links() if l["kind"] in (fitz.LINK_GOTO, fitz.LINK_NAMED)]
#         except:
#             break

#         for link in links:
#             try:
#                 rect = fitz.Rect(link['from'])
#                 link_text = page.get_text("text", clip=rect).strip()
#                 target_page = link.get("page") + 1  # Convert to 1-based
#                 if link_text:
#                     toc_data.append({
#                         "Link Text": link_text,
#                         "Target Page": target_page
#                     })
#             except:
#                 continue

#         page_num += 1
#         if page_num >= doc.page_count:
#             break

#         # Heuristic to see if next page is still part of TOC
#         try:
#             nxt_txt = doc.load_page(page_num).get_text("text")
#         except:
#             break
#         if not any(kw in nxt_txt for kw in ["SECTION", "....", "INTRODUCTION"]):
#             break

#     if not toc_data:
#         doc.close()
#         return None

#     df_links = pd.DataFrame(toc_data)

#     # Clean link text (remove trailing ....stuff)
#     def clean_text(txt):
#         return re.sub(r'\.{2,}.*', '', txt).strip()

#     df_links["Link Text"] = df_links["Link Text"].apply(clean_text)
#     df_links["Type"] = df_links["Link Text"].apply(lambda x: "Section" if "SECTION" in x.upper() else "Subject")

#     # Remove "SECTION" prefix for a cleaned version
#     def remove_section_prefix(txt):
#         return re.sub(r'^SECTION\s*[IVXLCD]+\s*:?', '', txt, flags=re.IGNORECASE).strip()

#     df_links["Cleaned Text"] = df_links["Link Text"].apply(remove_section_prefix)

#     # Build final table
#     entries = []
#     for _, row in df_links.iterrows():
#         entries.append({
#             "Type": row["Type"],
#             "Text": row["Link Text"],
#             "CleanedText": row["Cleaned Text"],
#             "StartingPage": row["Target Page"]
#         })

#     # We'll now figure out the page ranges for each item
#     toc_entries = []
#     current_section = None
#     current_section_start = None

#     for idx, entry in enumerate(entries):
#         if entry["Type"] == "Section":
#             # If we had a previous section open, close it
#             if current_section is not None:
#                 # find all items in toc_entries belonging to that section
#                 same_sec = [i for i,e in enumerate(toc_entries) if e["subject_section"] == current_section]
#                 if same_sec:
#                     last_i = same_sec[-1]
#                     if toc_entries[last_i]["ending_page_number"] is None:
#                         # close out at (this new start_page - 1)
#                         toc_entries[last_i]["ending_page_number"] = entry["StartingPage"] - 1
#                     for i2 in same_sec:
#                         if toc_entries[i2]["ending_page_number"] is None:
#                             toc_entries[i2]["ending_page_number"] = entry["StartingPage"] - 1
#                         if toc_entries[i2]["section_range"] is None:
#                             toc_entries[i2]["section_range"] = f"{current_section_start}-{entry['StartingPage'] - 1}"

#             # Start a new section
#             current_section = entry["Text"]
#             current_section_start = entry["StartingPage"]
#             toc_entries.append({
#                 "Type": entry["Type"],
#                 "subject": entry["Text"],
#                 "cleaned_subject": entry["CleanedText"],
#                 "starting_page_number": entry["StartingPage"],
#                 "ending_page_number": None,
#                 "subject_section": current_section,
#                 "section_range": None
#             })
#         else:
#             # Sub‐subject
#             if toc_entries and toc_entries[-1]["ending_page_number"] is None:
#                 prev_start = toc_entries[-1]["starting_page_number"]
#                 toc_entries[-1]["ending_page_number"] = max(prev_start, entry["StartingPage"] - 1)
#             toc_entries.append({
#                 "Type": entry["Type"],
#                 "subject": entry["Text"],
#                 "cleaned_subject": entry["CleanedText"],
#                 "starting_page_number": entry["StartingPage"],
#                 "ending_page_number": None,
#                 "subject_section": current_section,
#                 "section_range": None
#             })

#     # Close out the last section up to doc end
#     if toc_entries:
#         last_entry = toc_entries[-1]
#         try:
#             doc_page_count = doc.page_count
#         except:
#             doc_page_count = 9999  # fallback
#         if last_entry["ending_page_number"] is None:
#             last_entry["ending_page_number"] = doc_page_count

#         last_sec = last_entry["subject_section"]
#         for e in toc_entries:
#             if e["subject_section"] == last_sec:
#                 if e["ending_page_number"] is None:
#                     e["ending_page_number"] = doc_page_count
#                 if e["section_range"] is None:
#                     e["section_range"] = f"{current_section_start}-{doc_page_count}"

#     doc.close()

#     toc_df = pd.DataFrame(toc_entries)
#     toc_df["subject_range"] = toc_df["starting_page_number"].astype(str) + " - " + toc_df["ending_page_number"].astype(str)
#     # Reorder columns
#     toc_df = toc_df[
#         [
#             "Type", "subject", "cleaned_subject", "subject_range", 
#             "subject_section", "section_range", "starting_page_number", "ending_page_number",
#         ]
#     ]

#     return toc_df


# def extract_pdf_pages(pdf_path: str, start_page: int, end_page: int, output_buffer: io.BytesIO):
#     """
#     Extract pages [start_page..end_page] (0-based) from pdf_path,
#     writing them into in-memory output_buffer.
#     """
#     doc = fitz.open(pdf_path)
#     new_doc = fitz.open()
#     new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
#     new_doc.save(output_buffer)
#     new_doc.close()
#     doc.close()
#     output_buffer.seek(0)


# def merge_pdfs(pdf_chunks):
#     """
#     Merge multiple PDF BytesIO objects into a single in-memory PDF.
#     Returns a BytesIO of the merged PDF or None if empty.
#     """
#     if not pdf_chunks:
#         return None
#     merged_doc = fitz.open()
#     for chunk in pdf_chunks:
#         chunk.seek(0)
#         sub_doc = fitz.open(stream=chunk.read(), filetype="pdf")
#         merged_doc.insert_pdf(sub_doc)
#         sub_doc.close()
#     out_buf = io.BytesIO()
#     merged_doc.save(out_buf)
#     merged_doc.close()
#     out_buf.seek(0)
#     return out_buf

# ######################
# #    Streamlit App   #
# ######################

# def main():
#     # --- Sidebar ---
#     st.sidebar.title("PDF Splitter App")
#     st.sidebar.write("Use the main panel to upload or provide URL.")
    
#     st.title("PDF Splitter Wireframe Demo")

#     # Single PDF input
#     st.subheader("1. Provide a PDF by upload or URL (only one at a time)")
#     pdf_file = st.file_uploader("Upload PDF", type=["pdf"])
#     pdf_url = st.text_input("URL of PDF", value="")

#     # Must have either a file or a URL
#     if not pdf_file and not pdf_url:
#         st.warning("Please upload a PDF or provide a PDF URL.")
#         st.stop()

#     # Store in session state so we can display after extraction
#     if "pdf_data" not in st.session_state:
#         st.session_state["pdf_data"] = None  # (pdf_path, toc_df, pdf_name) or None

#     st.subheader("2. Process PDF(s)")
#     if st.button("Process / Extract TOC"):
#         try:
#             # Save to a local temp file so we have a path
#             local_path = "temp.pdf"
#             pdf_name = None

#             if pdf_file is not None:
#                 # Use uploaded file
#                 pdf_bytes = pdf_file.read()
#                 with open(local_path, "wb") as f:
#                     f.write(pdf_bytes)
#                 pdf_name = pdf_file.name
#             else:
#                 # Use the URL
#                 pdf_io = fetch_pdf_from_webpage(pdf_url)
#                 with open(local_path, "wb") as f:
#                     f.write(pdf_io.getbuffer())
#                 pdf_name = os.path.basename(pdf_url)

#             # Extract TOC
#             toc_df = extract_table_of_contents(local_path)
#             if toc_df is None or toc_df.empty:
#                 st.warning(f"No Table of Contents detected for {pdf_name}.")
#                 st.session_state["pdf_data"] = None
#             else:
#                 st.session_state["pdf_data"] = (local_path, toc_df, pdf_name)
#                 st.success(f"TOC extracted for {pdf_name}!")
#         except Exception as e:
#             st.error(f"Error processing PDF: {e}")
#             st.session_state["pdf_data"] = None

#     # If we have extracted data, show the TOC hierarchy
#     if st.session_state["pdf_data"] is not None:
#         pdf_path, toc_df, pdf_name = st.session_state["pdf_data"]
#         st.subheader("3. Select Sections / Subsections")

#         final_selection = []

#         # Sort the TOC by starting page
#         toc_df = toc_df.sort_values("starting_page_number", ascending=True)

#         # Identify all distinct "Section" rows
#         sections = toc_df[toc_df["Type"] == "Section"]

#         if sections.empty:
#             st.markdown("*No distinct 'Section' headings found. All might be 'Subjects':*")
#             # Possibly just show them as a flat list
#             for idx_sub, sub_row in toc_df.iterrows():
#                 sub_label = sub_row["subject"]
#                 sub_checked = st.checkbox(sub_label, value=False, key=f"sub_{idx_sub}")
#                 if sub_checked:
#                     final_selection.append(idx_sub)
#         else:
#             # For each Section, create an expander
#             for idx_sec, sec_row in sections.iterrows():
#                 section_label = sec_row["subject"]  # e.g. "SECTION I"
#                 with st.expander(section_label):
#                     # Show a top-level checkbox for the entire section
#                     sec_checked = st.checkbox(
#                         "Select entire section",
#                         value=False,
#                         key=f"section_{idx_sec}"
#                     )
#                     if sec_checked:
#                         final_selection.append(sec_row.name)

#                     # Sub-sections belonging to this section
#                     sub_df = toc_df[
#                         (toc_df["subject_section"] == sec_row["subject"]) & 
#                         (toc_df["Type"] == "Subject")
#                     ]
#                     if not sub_df.empty:
#                         for sdx, sub_row in sub_df.iterrows():
#                             # Indent with bullet
#                             sub_label = f"- {sub_row['subject']}"
#                             sub_checked = st.checkbox(
#                                 sub_label,
#                                 value=False,
#                                 key=f"sub_{idx_sec}_{sdx}",
#                                 help=f"Pages {sub_row['subject_range']}",
#                                 # Using CSS class to indent
#                                 label_visibility="visible"
#                             )
#                             # We can do a small hack to add a CSS class:
#                             st.markdown(
#                                 f"<div class='subsection-checkbox'></div>",
#                                 unsafe_allow_html=True
#                             )

#                             if sub_checked:
#                                 final_selection.append(sub_row.name)

#             # Also check if there are "Subject" rows not associated with any "Section"
#             unassigned_subjects = toc_df[
#                 (toc_df["Type"] == "Subject") & 
#                 (~toc_df["subject_section"].isin(sections["subject"].unique()))
#             ]
#             if not unassigned_subjects.empty:
#                 st.markdown("**Subjects not under a recognized Section**:")
#                 for idx_sub, sub_row in unassigned_subjects.iterrows():
#                     sub_label = sub_row["subject"]
#                     sub_checked = st.checkbox(sub_label, value=False, key=f"unassigned_{idx_sub}")
#                     if sub_checked:
#                         final_selection.append(idx_sub)

#         st.subheader("4. Download Options")
#         if final_selection:
#             # Build separate sub‐PDFs for each selection
#             sub_pdfs = []
#             for row_idx in final_selection:
#                 row = toc_df.loc[row_idx]
#                 start_page = int(row["starting_page_number"]) - 1  # zero-based
#                 end_page = int(row["ending_page_number"]) - 1

#                 out_buf = io.BytesIO()
#                 extract_pdf_pages(pdf_path, start_page, end_page, out_buf)

#                 # Generate a sanitized filename from the subject
#                 clean_sub = row["cleaned_subject"][:50].replace(" ", "_").replace("/", "_").replace("\\", "_")
#                 if not clean_sub:
#                     clean_sub = f"section_{start_page+1}"
#                 fname = clean_sub + ".pdf"
#                 sub_pdfs.append((fname, out_buf))

#             # Merge them all into a single PDF as well
#             merged_pdf = merge_pdfs([sp[1] for sp in sub_pdfs])

#             # "Download PDF (Merged)" button
#             if merged_pdf is not None:
#                 st.download_button(
#                     label="Download PDF (Merged)",
#                     data=merged_pdf.getvalue(),
#                     file_name="merged_selected_sections.pdf",
#                     mime="application/pdf",
#                 )

#             # "Download ZIP" with each sub‐PDF + the merged PDF
#             zip_buffer = io.BytesIO()
#             with zipfile.ZipFile(zip_buffer, "w") as zf:
#                 for (fname, buf) in sub_pdfs:
#                     zf.writestr(fname, buf.getvalue())
#                 if merged_pdf is not None:
#                     zf.writestr("merged_selected_sections.pdf", merged_pdf.getvalue())
#             zip_buffer.seek(0)

#             st.download_button(
#                 label="Download ZIP (sub-PDFs + merged)",
#                 data=zip_buffer,
#                 file_name="selected_sections.zip",
#                 mime="application/octet-stream",
#             )
#         else:
#             st.info("No sections/subsections selected.")
#     else:
#         st.info("No PDF / TOC available to select from. Upload or process above.")


# if __name__ == "__main__":
#     main()




import streamlit as st
import requests
from bs4 import BeautifulSoup
import io
import fitz  # PyMuPDF
import re
import zipfile
import pandas as pd
import os

###########################################
# Page Configuration & Custom CSS
###########################################
st.set_page_config(page_title="DRHP Splitter", layout="wide")

# --- Updated CSS ---
# Removed the white box styling for the checkbox container.
CUSTOM_CSS = """
<style>
    /* Reset default boldness for all checkbox label texts */
    .stCheckbox label div {
        font-weight: normal !important;
    }
    /* Style for Section Checkbox Labels */
    .stCheckbox label div:contains('SECTION') {
        font-size: 1.1rem !important;
        font-weight: bold !important;
        display: block !important;
        margin-bottom: 0.3rem !important;
    }
    /* Style for non-SECTION checkbox labels */
    .stCheckbox label div:not(:contains('SECTION')) {
        font-size: 1rem !important;
        display: block !important;
        margin-bottom: 0.1rem !important;
    }
    /* Modified Checkbox Container: removed border, background, padding and margin */
    .checkbox-scroll-container {
        max-height: 450px;
        overflow-y: auto;
        margin-bottom: 0;
    }
    /* Correct Tooltip Position for Help Icons */
    .stCheckbox {
       display: flex !important;
       align-items: baseline !important;
    }
    .stCheckbox [data-testid="stMarkdownContainer"] {
      order: 1;
      margin-right: 0.5em;
      flex-grow: 1;
      text-align: left;
    }
   .stCheckbox  .tooltip {
      order: 2;
      flex-shrink: 0;
      margin-left: auto;
     }
    /* Remove top white bar above "Select Sections/Subsections" */
    div.st-br {
        margin-top: 0px !important;
        padding-top: 0px !important;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

###########################################
# Utility Functions (No changes needed)
###########################################
def fetch_pdf_from_webpage(url: str) -> io.BytesIO:
    if url.lower().strip().endswith('.pdf'):
        pdf_resp = requests.get(url)
        if pdf_resp.status_code != 200:
            raise ValueError(f"Failed to download PDF from {url}")
        return io.BytesIO(pdf_resp.content)
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"Failed to retrieve the webpage: {url}")
    soup = BeautifulSoup(response.content, 'html.parser')
    iframe = soup.find('iframe')
    if iframe:
        interim_url = iframe.get('src', '')
        pdf_url = interim_url.split('file=')[1] if 'file=' in interim_url else interim_url
    else:
        pdf_url = url
    pdf_url = pdf_url.strip()
    if not pdf_url.lower().endswith('.pdf'):
        raise ValueError('URL does not point to a PDF file')
    pdf_resp = requests.get(pdf_url)
    if pdf_resp.status_code != 200:
        raise ValueError(f"Failed to download PDF from {pdf_url}")
    return io.BytesIO(pdf_resp.content)

def extract_table_of_contents(pdf_path: str):
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        st.error(f"Error opening PDF: {e}")
        return None
    toc_start_page = None
    for page_num in range(min(6, doc.page_count)):
        try:
            page = doc.load_page(page_num)
            text = page.get_text("text")
            if "Contents" in text or "TABLE OF CONTENTS" in text:
                toc_start_page = page_num
                break
        except:
            continue
    if toc_start_page is None:
        doc.close()
        return None
    toc_data = []
    page_num = toc_start_page
    while page_num < doc.page_count:
        try:
            page = doc.load_page(page_num)
            links = [l for l in page.get_links() if l["kind"] in (fitz.LINK_GOTO, fitz.LINK_NAMED)]
        except:
            break
        for link in links:
            try:
                rect = fitz.Rect(link['from'])
                link_text = page.get_text("text", clip=rect).strip()
                target_page = link.get("page", -1) + 1
                if link_text and target_page > 0:
                    toc_data.append({
                        "Link Text": link_text,
                        "Target Page": target_page
                    })
            except:
                continue
        page_num += 1
        if page_num >= doc.page_count:
            break
        try:
            nxt_txt = doc.load_page(page_num).get_text("text")
        except:
            break
        if not any(kw in nxt_txt for kw in ["SECTION", "....", "INTRODUCTION"]):
            break
    if not toc_data:
        doc.close()
        return None
    df = pd.DataFrame(toc_data)
    def clean_text(txt):
        return re.sub(r'\.{2,}.*', '', txt).strip()
    df["Link Text"] = df["Link Text"].apply(clean_text)
    df["Type"] = df["Link Text"].apply(lambda x: "Section" if "SECTION" in x.upper() else "Subject")
    def remove_section_prefix(txt):
        return re.sub(r'^SECTION\s*[IVXLCD]+\s*:?', '', txt, flags=re.IGNORECASE).strip()
    df["Cleaned Text"] = df["Link Text"].apply(remove_section_prefix)
    entries = []
    for _, row in df.iterrows():
        entries.append({
            "Type": row["Type"],
            "Text": row["Link Text"],
            "CleanedText": row["Cleaned Text"],
            "StartingPage": row["Target Page"]
        })
    toc_entries = []
    current_section = None
    current_section_start = None
    for idx, entry in enumerate(entries):
        if entry["Type"] == "Section":
            if current_section is not None:
                same_sec = [i for i, e in enumerate(toc_entries) if e["subject_section"] == current_section]
                if same_sec:
                    last_i = same_sec[-1]
                    if toc_entries[last_i]["ending_page_number"] is None:
                        toc_entries[last_i]["ending_page_number"] = entry["StartingPage"] - 1
                    for i2 in same_sec:
                        if toc_entries[i2]["ending_page_number"] is None:
                            toc_entries[i2]["ending_page_number"] = entry["StartingPage"] - 1
                        if toc_entries[i2]["section_range"] is None:
                            toc_entries[i2]["section_range"] = f"{current_section_start}-{entry['StartingPage'] - 1}"
            current_section = entry["Text"]
            current_section_start = entry["StartingPage"]
            toc_entries.append({
                "Type": entry["Type"],
                "subject": entry["Text"],
                "cleaned_subject": entry["CleanedText"],
                "starting_page_number": entry["StartingPage"],
                "ending_page_number": None,
                "subject_section": current_section,
                "section_range": None
            })
        else:
            if toc_entries and toc_entries[-1]["ending_page_number"] is None:
                prev_start = toc_entries[-1]["starting_page_number"]
                toc_entries[-1]["ending_page_number"] = max(prev_start, entry["StartingPage"] - 1)
            toc_entries.append({
                "Type": entry["Type"],
                "subject": entry["Text"],
                "cleaned_subject": entry["CleanedText"],
                "starting_page_number": entry["StartingPage"],
                "ending_page_number": None,
                "subject_section": current_section,
                "section_range": None
            })
    if toc_entries:
        last_entry = toc_entries[-1]
        try:
            doc_page_count = doc.page_count
        except:
            doc_page_count = 9999
        if last_entry["ending_page_number"] is None:
            last_entry["ending_page_number"] = doc_page_count
        last_sec = last_entry["subject_section"]
        for e in toc_entries:
            if e["subject_section"] == last_sec:
                if e["ending_page_number"] is None:
                    e["ending_page_number"] = doc_page_count
                if e["section_range"] is None:
                    e["section_range"] = f"{current_section_start}-{doc_page_count}"
    doc.close()
    toc_df = pd.DataFrame(toc_entries)
    toc_df["subject_range"] = toc_df["starting_page_number"].astype(str) + " - " + toc_df["ending_page_number"].astype(str)
    toc_df = toc_df[
        [
            "Type", "subject", "cleaned_subject", "subject_range",
            "subject_section", "section_range", "starting_page_number", "ending_page_number",
        ]
    ]
    return toc_df

def extract_pdf_pages(pdf_path: str, start_page: int, end_page: int, output_buffer: io.BytesIO):
    doc = fitz.open(pdf_path)
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
    new_doc.save(output_buffer)
    new_doc.close()
    doc.close()
    output_buffer.seek(0)

def merge_pdfs(pdf_chunks):
    if not pdf_chunks:
        return None
    merged_doc = fitz.open()
    for chunk in pdf_chunks:
        chunk.seek(0)
        sub_doc = fitz.open(stream=chunk.read(), filetype="pdf")
        merged_doc.insert_pdf(sub_doc)
        sub_doc.close()
    out_buf = io.BytesIO()
    merged_doc.save(out_buf)
    merged_doc.close()
    out_buf.seek(0)
    return out_buf

###########################################
# Checkbox Logic (No changes)
###########################################
def on_parent_change(parent_key, child_keys):
    new_val = st.session_state[parent_key]
    for ck in child_keys:
        st.session_state[ck] = new_val

def on_child_change(parent_key, child_keys):
    if all(st.session_state.get(ck, False) for ck in child_keys):
        st.session_state[parent_key] = True
    else:
        st.session_state[parent_key] = False

###########################################
# Main Streamlit App
###########################################
def main():
    st.sidebar.title("DRHP Splitter App")
    st.sidebar.write("")
    st.sidebar.write("Upload a DRHP PDF or provide a DRHP URL.")

    col1, col2 = st.columns([1, 12])
    with col1:
        st.image("logo.png", width=75)
    with col2:
        st.title("DRHP Splitter")
    
    pdf_file = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="hidden")
    pdf_url = st.text_input("Enter URL", value="", label_visibility="visible")

    if not pdf_file and not pdf_url:
        st.info("Please upload a PDF or enter a URL.")
        st.stop()

    def clear_old_checkboxes():
        for k in list(st.session_state.keys()):
            if k.startswith("toc_"):
                del st.session_state[k]

    if "pdf_data" not in st.session_state:
        st.session_state["pdf_data"] = None

    if pdf_url and (pdf_url != st.session_state.get("last_url", "")):
        st.session_state["last_url"] = pdf_url
        clear_old_checkboxes()
        try:
            pdf_io = fetch_pdf_from_webpage(pdf_url)
            with open("temp.pdf", "wb") as f:
                f.write(pdf_io.getbuffer())
            pdf_name = os.path.basename(pdf_url)
            toc_df = extract_table_of_contents("temp.pdf")
            if toc_df is None or toc_df.empty:
                st.warning(f"No TOC found for {pdf_name}.")
                st.session_state["pdf_data"] = None
            else:
                st.session_state["pdf_data"] = ("temp.pdf", toc_df, pdf_name)
                
        except Exception as e:
            st.error(f"Error processing URL PDF: {e}")
            st.session_state["pdf_data"] = None

    elif pdf_file and (pdf_file.name != st.session_state.get("last_file", "")):
        st.session_state["last_file"] = pdf_file.name
        clear_old_checkboxes()
        try:
            pdf_bytes = pdf_file.read()
            with open("temp.pdf", "wb") as f:
                f.write(pdf_bytes)
            pdf_name = pdf_file.name
            toc_df = extract_table_of_contents("temp.pdf")
            if toc_df is None or toc_df.empty:
                st.warning(f"No TOC found for {pdf_name}.")
                st.session_state["pdf_data"] = None
            else:
                st.session_state["pdf_data"] = ("temp.pdf", toc_df, pdf_name)
                st.success(f"TOC extracted for {pdf_name}!")
        except Exception as e:
            st.error(f"Error processing uploaded PDF: {e}")
            st.session_state["pdf_data"] = None

    if st.session_state["pdf_data"] is not None:
        pdf_path, toc_df, pdf_name = st.session_state["pdf_data"]

        x = st.expander("Select Sections and Subsections", expanded=True)
        with x:
            mapping = {}
            child2parent = {}
            final_keys = []
            current_parent_key = None
            sorted_toc = toc_df.sort_values("starting_page_number").reset_index(drop=True)

            for idx, row in sorted_toc.iterrows():
                key = f"toc_{idx}"
                final_keys.append((idx, key))

            for idx, row in sorted_toc.iterrows():
                key = f"toc_{idx}"
                if row["Type"] == "Section":
                    current_parent_key = key
                    mapping[current_parent_key] = []
                else:
                    if current_parent_key is not None:
                        mapping[current_parent_key].append(key)
                        child2parent[key] = current_parent_key
                    else:
                        mapping[key] = []

            st.markdown('<div class="checkbox-scroll-container">', unsafe_allow_html=True)

            # Helper function to determine indent level.
            # Sections (Type=="Section") get level 0.
            # For subjects, if the cleaned subject starts with a numbering pattern (e.g., "1.1" or "1.1.1"),
            # we use the count of dots as the level (so "1.1" -> level 1, "1.1.1" -> level 2).
            # Otherwise, default to level 1.
            def get_indent_level(row):
                if row["Type"] == "Section":
                    return 0
                m = re.match(r'^(\d+(\.\d+)+)', row["cleaned_subject"])
                if m:
                    return m.group(1).count('.')
                return 1

            for idx, row in sorted_toc.iterrows():
                key = f"toc_{idx}"
                indent_level = get_indent_level(row)
                if indent_level > 0:
                    # Use st.columns to simulate tab indentation
                    cols = st.columns([indent_level, 10])
                    with cols[1]:
                        if row["Type"] == "Section":
                            st.checkbox(
                                label=row["subject"],
                                key=key,
                                value=st.session_state.get(key, False),
                                on_change=on_parent_change,
                                args=(key, mapping.get(key, [])),
                                
                                
                            )
                        else:
                            parent_key = child2parent.get(key, None)
                            st.checkbox(
                                label=row["subject"],
                                key=key,
                                value=st.session_state.get(key, False),
                                on_change=on_child_change if parent_key else None,
                                args=(parent_key, mapping.get(parent_key, [])) if parent_key else (),
                
                            )
                else:
                    if row["Type"] == "Section":
                        st.checkbox(
                            label=row["subject"],
                            key=key,
                            value=st.session_state.get(key, False),
                            on_change=on_parent_change,
                            args=(key, mapping.get(key, [])),
            
                        )
                    else:
                        parent_key = child2parent.get(key, None)
                        st.checkbox(
                            label=row["subject"],
                            key=key,
                            value=st.session_state.get(key, False),
                            on_change=on_child_change if parent_key else None,
                            args=(parent_key, mapping.get(parent_key, [])) if parent_key else (),
                    
                        )
            st.markdown("</div>", unsafe_allow_html=True)

            final_selection = [idx for (idx, k) in final_keys if st.session_state.get(k, False)]

        st.subheader("Download Options")
        if final_selection:
            sub_pdfs = []
            for row_idx in final_selection:
                row = sorted_toc.loc[row_idx]
                start_page = int(row["starting_page_number"]) - 1
                end_page = int(row["ending_page_number"]) - 1
                out_buf = io.BytesIO()
                extract_pdf_pages(pdf_path, start_page, end_page, out_buf)
                clean_sub = row["cleaned_subject"][:50].replace(" ", "").replace("/", "").replace("\\", "_")
                if not clean_sub:
                    clean_sub = f"section_{start_page+1}"
                fname = clean_sub + ".pdf"
                sub_pdfs.append((fname, out_buf))

            merged_pdf = merge_pdfs([sp[1] for sp in sub_pdfs])

            col1, col2 = st.columns(2)
            with col1:
                if merged_pdf is not None:
                    st.download_button(
                        label="Download single PDF (Selected sections)",
                        data=merged_pdf.getvalue(),
                        file_name="merged_selected_sections.pdf",
                        mime="application/pdf",
                    )
            with col2:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for (fname, buf) in sub_pdfs:
                        zf.writestr(fname, buf.getvalue())
                    if merged_pdf is not None:
                        zf.writestr("merged_selected_sections.pdf", merged_pdf.getvalue())
                zip_buffer.seek(0)
                st.download_button(
                    label="Download ZIP File (Individual sections + Merged file)",
                    data=zip_buffer,
                    file_name="selected_sections.zip",
                    mime="application/octet-stream",
                    type="secondary",
                )
        else:
            st.info("No sections selected.")
    else:
        st.info("Upload PDF or provide URL to see TOC.")

if __name__ == "__main__":
    main()

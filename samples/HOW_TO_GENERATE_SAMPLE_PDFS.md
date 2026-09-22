# Sample Case PDFs — Generation Instructions

This package does not ship pre-built PDF files (the hiring manager should generate them locally to avoid binary artifacts in the package). You need to create **2 sample case PDFs** that candidates will upload during the exercise.

## Sample Case 1 — Criminal SLP (matches the sample outputs)

The sample outputs in `samples/` were generated based on this hypothetical case. Create a scanned-looking PDF with the following content:

### Case 1 Content

**File name:** `sample_case_1.pdf`

**Required text content (that OCR should be able to extract):**

```
IN THE SUPREME COURT OF INDIA
CRIMINAL APPELLATE JURISDICTION

SPECIAL LEAVE PETITION (CRIMINAL) NO. _____ OF 2026

BETWEEN:
Rahul Bhikulal Kasat                                  ... Petitioner
                    VERSUS
The State of Maharashtra                              ... Respondent

SYNOPSIS

The present Special Leave Petition is preferred against the final
judgment and order dated 15.11.2025 passed by the High Court of
Judicature at Bombay in Criminal Appeal No. 1234/2024, whereby the
Hon'ble High Court was pleased to dismiss the appeal and confirm
the conviction of the Petitioner under Sections 120B and 302 of
the Indian Penal Code, 1860.

LIST OF DATES

15.03.2023  - FIR No. 234/2023 registered at Pune Police Station
              under Section 304A IPC alleging accidental death.

02.07.2023  - Investigation revealed suspicious circumstances;
              supplementary chargesheet filed under Section 302
              read with Section 120B IPC.

20.11.2024  - Sessions Court, Pune convicted the Petitioner.

15.11.2025  - Bombay High Court dismissed Criminal Appeal.

GROUNDS

A. The Hon'ble High Court failed to appreciate that the CCTV
   footage relied upon by the prosecution was produced without
   a certificate under Section 65B(4) of the Indian Evidence Act,
   1872, rendering it inadmissible.

B. The FIR was initially registered under Section 304A for
   accidental death and subsequently converted to Section 302.
   The Petitioner was not afforded sufficient opportunity to
   cross-examine witnesses whose statements were recorded under
   the original charge.

C. The motive alleged by the prosecution — a financial dispute
   between the Petitioner and the deceased — was demolished by
   Prosecution Witness PW-7, who stated under cross-examination
   that the dispute had been amicably settled six months prior
   to the incident.

D. The chain of circumstantial evidence is broken and does not
   satisfy the Sharad Birdhichand standard.

PRAYER

In the premises, it is most respectfully prayed that this
Hon'ble Court may be pleased to:

(a) Grant special leave to appeal against the impugned judgment;
(b) Set aside the conviction and sentence;
(c) Pass such further or other orders as this Hon'ble Court may
    deem fit and proper in the facts and circumstances of the
    case.

                                    Drawn & Filed by:
                                    Atul Babasaheb Deshmukh
                                    Advocate on Record
                                    Supreme Court of India
```

### How to Generate the PDF

**Option A — From plain text (cleanest, easy OCR):**

```python
# generate_sample_pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import cm

doc = SimpleDocTemplate("sample_case_1.pdf", pagesize=A4,
                        leftMargin=2*cm, rightMargin=2*cm,
                        topMargin=2*cm, bottomMargin=2*cm)
styles = getSampleStyleSheet()
story = []

with open("case_1_text.txt", "r") as f:
    for para in f.read().split("\n\n"):
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["Normal"]))
        story.append(Spacer(1, 0.3*cm))

doc.build(story)
```

**Option B — Scanned-look (more realistic for OCR testing):**

1. Generate the PDF as above.
2. Convert each page to an image using `pdf2image` at 150 DPI.
3. Apply slight rotation (±1°) and Gaussian noise to simulate scanning.
4. Re-embed images into a new PDF.

This forces candidates to use real OCR (Document AI or pytesseract) rather than shortcutting with `pypdf.extract_text()`.

**Recommendation:** Ship Option A to candidates for Day 1–2 speed, but have Option B available as a harder variant for senior roles.

## Sample Case 2 — Civil Matter (different content for diverse testing)

Create a second PDF, `sample_case_2.pdf`, with content from a different legal domain. Suggested: a civil suit involving contract breach and electronic evidence (so it naturally surfaces different dimensions from the corpus).

Example subject matter:
- Commercial contract dispute with WhatsApp screenshots as evidence
- Question of Section 65B certification for the screenshots
- Question of jurisdiction under the arbitration clause

Parties:
- "Anita Enterprises Private Limited vs. Vikas Constructions LLP"
- Court: Bombay High Court, Commercial Division
- Sections: Arbitration Act 1996 § 9, IEA § 65B, Specific Relief Act

This gives you a second test case that hits the `j_0004`, `j_0007`, `j_0011`, `j_0012` judgments in the corpus (electronic evidence + quashing commercial dispute).

## Verifying Your Sample PDFs

After generating, verify with:

```bash
# Extract text, confirm it's legible
pdftotext sample_case_1.pdf -
```

The extracted text should contain the key phrases: "Section 65B", "Section 302", "120B", "Rahul Bhikulal Kasat", "Maharashtra", "prosecution witness", "motive".

If using Option B (scanned), verify with pytesseract instead:

```python
import pytesseract
from pdf2image import convert_from_path

pages = convert_from_path("sample_case_1.pdf", dpi=200)
text = "\n".join(pytesseract.image_to_string(p) for p in pages)
print(text[:2000])
```

## Final File Placement

Once generated, place the PDFs at:

```
Lawapp_Project/samples/sample_case_1.pdf
Lawapp_Project/samples/sample_case_2.pdf
```

Then regenerate the package zip you send to candidates.

# Team Academy certificate issuance (Level 1 LinkedIn integration)

## Supported course codes

Use these stable codes in `input/completions.csv`:

| Course | Code |
|---|---|
| Agentic AI for Financial Process Automation | `AIF` |
| Microsoft Office | `MSO` |
| Python | `PYTHON` |
| Data Analytics | `DA` |
| Generative AI | `GENAI` |

The `course_name` column should contain the exact course title to print on the certificate. The code is used in the certificate ID. Existing codes must not be renamed after certificates have been issued.

## How an authorized member issues a certificate

1. Confirm the student's full name, exact course title and actual completion date.
2. Add one row to `input/completions.csv` with the columns shown below.
3. Use the completion date as `YYYY-MM-DD` and put the approving member's staff code/initials in `approved_by` (not a private email address or phone number).
4. Commit and push the CSV change to the GitHub repository. This commit by an authorized member is the approval action.
5. GitHub Actions runs `scripts/issue.py`, creates the PDF and preview, adds a registry record and pushes the generated files.
6. After GitHub Pages has deployed, share the PDF from `docs/pdf/` and the verification URL with the student manually.

Example:

```csv
student,course_code,course_name,completion_date,approved_by
Aarav Kumar,AIF,"Agentic AI for Financial Process Automation",2026-11-25,TA-MEMBER-07
Mira Shah,DA,"Data Analytics Professional Certificate",2026-11-26,TA-MEMBER-12
```

## Certificate ID format

`TA-YYYY-COURSECODE-NNNN`, for example `TA-2026-AIF-0001`.

- `TA`: Team Academy
- `YYYY`: year the certificate is issued (not necessarily the completion year)
- `COURSECODE`: one of the stable codes above
- `NNNN`: next sequence for that issue year and course code

The script assigns the ID. Members and students must not choose or edit it. Re-running the workflow for the same student, course and completion date regenerates the existing certificate with its existing ID. A different completion date is treated as a separate completion and receives a new ID.

## Student's LinkedIn steps

1. Open the individual verification URL or scan the QR code on the PDF.
2. Confirm the page says **Valid certificate · Active**.
3. Click **Add to LinkedIn Profile**.
4. In LinkedIn's Licenses & Certifications form, enter the course title, select the official **Team Academy** issuing organization, and enter the issue date, credential ID and credential URL shown on the verification page.
5. Save the entry.

LinkedIn currently does not autofill the certificate fields from the provider button; students enter them themselves. The credential URL links back to Team Academy's public verification record.

## Configure Team Academy's official LinkedIn button URL

1. Visit <https://addtoprofile.linkedin.com/> while signed in to LinkedIn.
2. Create the certification Add to Profile button and select the existing **Team Academy** LinkedIn Page.
3. Copy the static URL LinkedIn generates.
4. Replace the value of `TEAM_ACADEMY_LINKEDIN_ADD_URL` in `docs/config.js` with that exact URL, keeping the quotation marks.
5. Commit and push `docs/config.js`.

Until this is configured, the button uses LinkedIn's generic certification form URL. The provider-generated URL is preferred so the official issuer page is associated with the button experience.

## GitHub Pages and Actions setup

- In GitHub, open **Settings → Pages** and confirm the site is deployed from the `main` branch and `/docs` folder (or preserve the existing Pages source if it is already working).
- Open **Settings → Actions → General → Workflow permissions** and enable **Read and write permissions**, because the workflow commits generated certificates and registry updates.
- Push changes to `input/completions.csv` to trigger issuance. You can also run **Actions → Issue certificates → Run workflow** to regenerate the output.
- Wait for the workflow to finish successfully and for Pages to publish before sharing the URL.

## Important privacy and operational notes

- The public verification registry contains student names, course titles, dates, certificate IDs and status. The repository's CSV also contains student and approver information. Anyone who can access a public repository can read these files. Obtain appropriate consent and use staff codes rather than personal contact details. Consider a private source repository with a public Pages publishing workflow if student data must not be exposed in the repository.
- The existing repository's certificate template is used for every course unless a course-specific image exists at `templates/<CODE>.jpg`. Add course-specific artwork only if you want a different design per course.
- The SHA-256 value is a file-integrity checksum, not a digital signature. Level 1 verification checks the public Team Academy registry; it does not provide cryptographic issuer authentication.
- Manual delivery is intentional: this workflow does not email students. An authorized member downloads the generated PDF and sends it through Team Academy's chosen channel.
- To revoke a certificate, change its `status` to `revoked` in `docs/data/certificates.json` and commit the change. Do not remove the record; the verification page will then show it as revoked.

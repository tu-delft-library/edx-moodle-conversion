# OLX Importer

The OLX importer accepts an extracted course directory or a `.tar.gz` export through the `ocw` command and OLX GUI.

## Structure mapping

OpenEdx chapters become Moodle sections. Sequentials become Moodle subsections when the sequential sections option
is enabled. Verticals become Moodle pages and preserve the order of supported components.

## Supported content

* Static HTML and source HTML fragments
* Images and locally exported static files
* PDFs and other referenced files
* Syllabus and readings content
* Video placeholders and Video Router source metadata

Unsupported interactive components are skipped while the surrounding page is retained.

## Warnings and checks

The parser warns about missing static files, content still hosted on edX infrastructure, unsupported components, and
ambiguous video pairing. The OLX CLI and GUI also run post-build chapter, subsection, and page parity checks.

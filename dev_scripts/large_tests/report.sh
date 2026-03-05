LARGE_TEST_DOCS_DIR="$(dirname $(realpath $0))/../../tests/test_docs_large/all_documents"
VALID_DOCS="pdf|docx|doc|xlsx|xls|pptx|ppt|odt|ods|odp|odg|jpg|jpeg|gif|png"

# Expected outputs that can be safely discarted from the analysis
EXPECTED_CONTAINER_OUTPUTS=$(
python - <<EOF
lines="""pdfinfo:
X X /tmp/page-X.ppm
Converting page X/X to pixels
Converting page X/X from pixels to searchable PDF
Converting to PDF using LibreOffice
Safe PDF created
Compressing PDF
Merging X pages into a single PDF
Converted document to pixels
Calculating number of pages
libreoffice: convert /tmp/input_file -> /tmp/input_file.pdf using filter : impress_pdf_Export
libreoffice: convert /tmp/input_file -> /tmp/input_file.pdf using filter : calc_pdf_Export
libreoffice: convert /tmp/input_file -> /tmp/input_file.pdf using filter : writer_pdf_Export
pdftoppm: Syntax Error (X): Dictionary key must be a name object
Result: SUCCESS
Result: FAILURE
\[COMMAND\]
"""
print("\|".join(lines.replace(' ', '\ ').split('\n'))[:-2])
EOF
)

#-------------------------------------------------#
#                                                 #
#        F I L T E R   F U N C T I O N S          #
#                                                 #
#  Functions to transform stdin into stdout       #
#-------------------------------------------------#
replace_nums_with_x() {
    # Aggregates results by combining numbers: 1234 -> X
    # pdftoppm: "Ilegal character" can take several forms
    sed -r 's/[0123456789]+/X/g' \
    | sed -r 's/Illegal character .*/Illegal character XXX/g'
}

count_similar() {
    sort | uniq -c | sort
}

find_all_docs() {
    find $LARGE_TEST_DOCS_DIR -regextype posix-extended \
            -regex ".*\.($VALID_DOCS)"
}

find_in_container_logs() {
    cat $1 | grep "${@:2}"
}

find_in_container_logs_print_file() {
    # find_in_container_logs but print the file name first
    cat $1 | grep -H "${@:2}"
}

container_output_exclude_expected() {
    grep -v "$EXPECTED_CONTAINER_OUTPUTS"
}

tsv_swap_columns() {
    # Swaps first with second column in tab-separated input
    awk -F'\t' '{temp=$1; $1=$2; $2=temp; printf("%s\t%s\n", $1, $2)}'
}

tsv_align_columns() {
    column -s $'\t' -t -c 4
}

indent() {
    sed 's/^/    /'
}

count_repeats() {
    sort | uniq -c | sort -r
}


#-------------------------------------------------#
#                                                 #
#        H E L P E R   F U N C T I O N S          #
#                                                 #
#-------------------------------------------------#

h1() {
    uppercase_title=$(echo $@ | tr '[:lower:]' '[:upper:]')
    echo -e "\n=== $uppercase_title ==="
}

h2() {
    echo -e "\n  $@"
}

#-------------------------------------------------#
#                                                 #
#     R E P O R T I N G   F U N C T I O N S       #
#                                                 #
#-------------------------------------------------#

report_composition() {
    h1 "test overview"

    h2 "Extensions breakdown (All available tests)"
    find_all_docs | sed 's/.*\.//' | count_repeats | indent
    h2 "File sizes breakdown (All available tests)"
    echo "0KB  -  10KB $(find $LARGE_TEST_DOCS_DIR -regextype posix-extended -regex ".*\.($VALID_DOCS)" -size -10k | wc -l )" | indent
    echo "10KB - 100KB $(find $LARGE_TEST_DOCS_DIR -regextype posix-extended -regex ".*\.($VALID_DOCS)" -size +10k -a -size -100k | wc -l )" | indent
    echo "100KB - 10MB $(find $LARGE_TEST_DOCS_DIR -regextype posix-extended -regex ".*\.($VALID_DOCS)" -size +100k -a -size -1M  | wc -l )" | indent
    echo "10MB - 100MB $(find $LARGE_TEST_DOCS_DIR -regextype posix-extended -regex ".*\.($VALID_DOCS)" -size +1M -a -size -10M | wc -l )" | indent
    echo "100MB+       $(find $LARGE_TEST_DOCS_DIR -regextype posix-extended -regex ".*\.($VALID_DOCS)" -size +10M | wc -l )" | indent
}

report_common_errors() {
    # Compute container output
    cat $1 \
        | replace_nums_with_x \
        | container_output_exclude_expected \
        > /tmp/container_output

	h1 "most common container output"
    h2 "Top 30:"
	cat /tmp/container_output | replace_nums_with_x | count_repeats | head -n 30
}


report_failure_reasons() {
    h1 "failure reasons"

    h2 "All failures:"
    cat $1 \
        | container_output_exclude_expected \
        | replace_nums_with_x \
        | count_repeats

    h1 "timeouts"
    h2 "Summary:"
    find_in_container_logs $1 "timed out after" | replace_nums_with_x | count_similar

    h2 "Affected files:"
    find_in_container_logs_print_file $1 "timed out after" \
        | sed -e 's/.container_log:/\t/g' \
        | tsv_swap_columns | sort | tsv_align_columns | indent
}

report_composition
report_common_errors $1
report_failure_reasons $2

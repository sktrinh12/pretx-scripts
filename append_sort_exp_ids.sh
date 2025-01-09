#!/bin/bash

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <input_file>"
  exit 1
fi

PARENT_DIR="./exp_ids"

RAW_INPUT_FILE="$1"
BASENAME="${RAW_INPUT_FILE%.*}"
PROTOCOL=$(echo "$BASENAME" | cut -d '.' -f3)
INSTANCE_TYPE=$(echo "$BASENAME" | cut -d '.' -f2)
INPUT_FILE1="${PARENT_DIR}/exp_ids_eln_writeup_${INSTANCE_TYPE}_${PROTOCOL}.txt"
INPUT_FILE2="${PARENT_DIR}/$1"
output_file="${PARENT_DIR}/_combined_exp_ids_eln_writeup_${INSTANCE_TYPE}_${PROTOCOL}.txt"

if [[ ! -f "$INPUT_FILE1" ]]; then
  echo "Error: File '${INPUT_FILE1}' not found."
  exit 1
fi

if [[ ! -f "$INPUT_FILE2" ]]; then
  echo "Error: File '${INPUT_FILE2}' not found."
  exit 1
fi

combined_exp_ids=$(cat "${INPUT_FILE1}" "${INPUT_FILE2}" | tr ',' '\n' | sort -n | uniq)

echo "$combined_exp_ids" | tr '\n' ',' | sed 's/,$/\n/' > "$output_file"

echo "Sorted exp_id files have been saved to $output_file."

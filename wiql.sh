#!/bin/bash

ORG_NAME="preludetx"
PROJECT_NAME="PreludeTx_Dotmatics_2024"
TEAM_NAME="PreludeTx_Dotmatics_2024%20Team"

API_URL="https://dev.azure.com/$ORG_NAME/$PROJECT_NAME/_apis/wit/wiql?api-version=7.0"

declare -A USERS=(
    [1]="Trinh, Spencer <strinh@rchsolutions.com>"
    [2]="Genaro Scavello"
)

echo "Select a user:"
for key in "${!USERS[@]}"; do
    echo "$key) ${USERS[$key]}"
done

read -p "Enter user number: " USER_NUM

if [[ -z "${USERS[$USER_NUM]}" ]]; then
    echo "Invalid selection!"
    exit 1
fi

SELECTED_USER="${USERS[$USER_NUM]}"

WIQL_QUERY=$(cat <<EOF
{
  "query": "SELECT
    [System.Id],
    [System.ChangedDate],
    [System.CreatedDate],
    [Microsoft.VSTS.Common.ClosedDate],
    [System.AssignedTo],
    [System.State],
    [System.Title],
    [System.WorkItemType],
    [Microsoft.VSTS.Scheduling.StoryPoints]
FROM WorkItems
WHERE
    [System.TeamProject] = 'PreludeTx_Dotmatics_2024' AND
    [System.AssignedTo] = '${SELECTED_USER}'
ORDER BY [System.ChangedDate] DESC"
}
EOF
)

WIQL_RESPONSE=$(curl -s -u ":$AZURE_DEVOPS_PAT" \
  -H "Content-Type: application/json" \
  -X POST \
  -d "$WIQL_QUERY" \
  "$API_URL")

WORK_ITEM_IDS=$(echo "$WIQL_RESPONSE" | jq -r '.workItems[].id' | tr '\n' ',' | sed 's/,$//')

if [ -z "$WORK_ITEM_IDS" ]; then
  echo "No work items found."
  exit 0
fi

FIELDS="System.Id,System.Title,System.AssignedTo,System.State,Microsoft.VSTS.Scheduling.StoryPoints,System.CreatedDate,Microsoft.VSTS.Common.ClosedDate,System.WorkItemType"
DETAILS_URL="https://dev.azure.com/$ORG_NAME/$PROJECT_NAME/_apis/wit/workitems?ids=$WORK_ITEM_IDS&fields=$FIELDS&api-version=7.0"

RESULTS=$(curl -s -u ":$AZURE_DEVOPS_PAT" "$DETAILS_URL")

echo $RESULTS | jq '.value[] | { 
  id: .id,
  title: .fields."System.Title",
  assignedTo: .fields."System.AssignedTo",
  state: .fields."System.State",
  workItem: .fields."System.WorkItemType",
  storyPoints: .fields."Microsoft.VSTS.Scheduling.StoryPoints",
  createdDate: .fields."System.CreatedDate",
  closedDate: .fields."Microsoft.VSTS.Common.ClosedDate"
}'

echo "═══════════════════════════════════════════════"
echo "       📊 PERFORMANCE STATISTICS SUMMARY"
echo "═══════════════════════════════════════════════"

echo "$RESULTS" | jq --arg user "$SELECTED_USER" '
  def parse_date:
    try (gsub("\\.[0-9]+Z$"; "Z") | fromdateiso8601) catch null;

  # Formatting functions
  def roundit(precision): (.*pow(10;precision)) | floor / pow(10;precision);
  def format_days:
    if . >= 30 then "\((. /30 | roundit(1))) months"
    elif . >= 7 then "\((. /7 | roundit(1))) weeks"
    else 
      . as $days |
      if $days >= 1 then "\(roundit(1)) days"
      else
        ($days * 24) as $hours |
        if $hours >= 1 then "\($hours | roundit(1)) hours"
        else "\($hours * 60 | roundit(1)) minutes"
        end
      end
    end;

  .value as $items |
  {
    total_stories: ($items | length),
    total_points: ($items | map(.fields."Microsoft.VSTS.Scheduling.StoryPoints" | numbers) | add // 0),
    avg_points: (
      ($items | length) as $count |
      if $count > 0 then
        ($items | map(.fields."Microsoft.VSTS.Scheduling.StoryPoints" | numbers) | add // 0) / $count
      else 0 end
    ),
    cycle_times: (
      $items |
      map(
        (.fields."System.CreatedDate" | parse_date) as $created |
        (.fields."Microsoft.VSTS.Common.ClosedDate" | parse_date) as $closed |
        if $created and $closed then ($closed - $created)/86400 else null end
      ) |
      [.[] | select(. > 0)] |
      if length > 0 then
        {
          avg: (add / length),
          total: length,
          min: min,
          max: max
        }
      else
        {avg: 0, total: 0}
      end
    ),
    states: (
      $items | group_by(.fields."System.State") | map({
        state: .[0].fields."System.State",
        count: length,
        points: (map(.fields."Microsoft.VSTS.Scheduling.StoryPoints" | numbers) | add // 0)
      })
    )
  } |
  {
    user: $user,
    total_stories: .total_stories,
    total_points: .total_points,
    avg_points: .avg_points | roundit(3),
    cycle_stats: {
      avg: (.cycle_times.avg | format_days),
      min: (.cycle_times.min | format_days),
      max: (.cycle_times.max | format_days),
      total_items: .cycle_times.total,
      raw_avg_days: (.cycle_times.avg | roundit(1))
    },
    states: .states
  }'

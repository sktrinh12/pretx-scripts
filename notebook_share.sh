#!/bin/bash

# need to run as sudo

SHARED_DATA="/srv/data/shared_data"

for userdir in /home/jupyter-*; do
    # check is a directory
    if [ ! -d "$userdir" ]; then
        continue
    fi

    username=$(basename "$userdir")
    USER_LINK="$userdir/shared_data"

    # Check if the symbolic link exists or if a file/directory with the same name exists
    if [ -L "$USER_LINK" ]; then
        echo "Symbolic link already exists for $username. Skipping."
    elif [ -e "$USER_LINK" ]; then
        echo "A file or directory named 'shared_data' exists in $username's home directory. Skipping."
    else
        # Create the symbolic link
        ln -s "$SHARED_DATA" "$USER_LINK"
        echo "Symbolic link created for $username."
    fi
done

echo "Update completed."

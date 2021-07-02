#!/bin/bash

# Enable globstar for Searching recursively 
shopt -s globstar
# Reset the Option Index in case getopts has been used previously in the same shell.
OPTIND=1 

function show_help() {
    echo "update.sh help"
    echo ""
    echo "This Script will update a given Version in all Dockerfiles present under the current directory"
    echo "If the old version can not be found, it does nothing"
    echo ""
    echo "usage:"
    echo "update.sh <old version> <new version>"
    echo ""
    echo "example:"
    echo "update.sh -o 8.9.1.44547 -n 9.0.0.12345"
    exit 0
}

##########
## Main ##
##########

OLD_VERSION=""
NEW_VERSION=""

while getopts ":h:o:n:" o; do
    case "${o}" in
        o)
            OLD_VERSION=${OPTARG}
            ;;
        n)
            NEW_VERSION=${OPTARG}
            ;;
        h)
            show_help
            ;;
        *)
            show_help
            ;;
    esac
done
shift $((OPTIND-1))

for i in ./**/Dockerfile; do 
    sed -i "s/${OLD_VERSION}/${NEW_VERSION}/g" $i
done

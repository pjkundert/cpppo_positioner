#!/bin/bash

DIR=${PWD}

# Array to store background process PIDs
declare -a PIDS

# Cleanup function to kill all background processes
cleanup() {
    echo "Cleaning up processes..."
    for pid in "${PIDS[@]}"; do
        if kill -0 $pid 2>/dev/null; then
            kill $pid
            echo "Killed process $pid"
        fi
    done
    
    # Remove virtual port symlinks if they exist
    rm -f ttyV[H0-9] 2>/dev/null
    
    exit 0
}

# Set up trap for script termination
trap cleanup SIGINT SIGTERM

echo "Creating virtual serial ports..."

# Create the hub
socat -d -d PTY,raw,echo=0,link=${DIR}/ttyV0 PTY,raw,echo=0,link=${DIR}/ttyVH &
PIDS+=($!)
sleep 1  # Give time for the ports to be created

# Create additional connected ports
socat -d -d PTY,raw,echo=0,link=${DIR}/ttyV1 GOPEN:${DIR}/ttyVH,raw,echo=0 &
PIDS+=($!)
socat -d -d PTY,raw,echo=0,link=${DIR}/ttyV2 GOPEN:${DIR}/ttyVH,raw,echo=0 &
PIDS+=($!)

echo "Virtual ports created:"
echo "  - ${DIR}/ttyV0 (hub input)"
echo "  - ${DIR}/ttyV1 (connected port)"
echo "  - ${DIR}/ttyV2 (connected port)"

echo "Waiting for first socat process to exit..."
echo "Press Ctrl+C to terminate all processes"

# Wait for the first socat process to exit
wait ${PIDS[0]}

echo "First process exited, cleaning up..."
cleanup

# Goal
Create a communication manager http server to manage tasks between chrome extension and python tasks.

# Design
The communication manager holds a queue of communication interactions. An "interaction" has:
- A unique id
- An input string
- An output string
- A status, among {PENDING, RUNNING, COMPLETED, FAILED}

The server provides APIs for:

- Adding a new interaction to the end of the queue. Only input string is needed, and server automatically assigns a unique id to the interaction. Then return id to caller.

- Peek the next interaction in the queue. The whole interaction object will be returned, including id, status, input, and output.

- Change response and status of the next interaction in the queue (only the next one in queue is modifiable), which returns the whole interaction object after update.
    - When an interaction is marked as completed, it is automatically removed from the queue.

- (debug) List all interactions in the queue.

# TODO

- Write the API spec and server metadata (e.g. port) into api.md file.

- Implement the communication manager server in Python in the current directory.

- Create a start_communication_manager.sh and start_communication_manager.bat file in parent directory ("src/") to start the server.

- Create a python client for the APIs, then create a debug purposed command line tool (using this client) to interact with the server.
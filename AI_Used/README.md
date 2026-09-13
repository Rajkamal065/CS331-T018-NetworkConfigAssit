# AI Usage & Raw Prompts Log

**Course:** CS331 — Computer Networks  
**Team ID:** T018  
**Project:** NetOps MCP Assistant: Safe Linux Network Automation  
**Team Members:** Sowpati Raj Kamal (23110319), Yalla Sai Teja (23110366), Pulakurthi Manohar (23110259), Guda Avinash Reddy (23110123), Jangam Sanjay (23110144), Gella Jaya Rama Krishna (23110115)

---

## AI Tools Used
- **ChatGPT (GPT-4o)** — Architecture exploration, protocol understanding (MCP, JSON-RPC), Linux networking concepts (iptables, tc, BBR), and troubleshooting.
- **Claude / Antigravity / Cursor** — Code generation, FastMCP tool implementation, test suite generation, debugging container environment, and terminal verification.
- **Groq API** — Integrated inside the application itself as the intent-interpretation engine.

---

## Raw Prompts Used

### Prompt 1
> I have designed my NetOps assistant with a GUI, assistant.py as the orchestrator, an LLM for natural-language interpretation, an MCP client/server boundary, a policy layer, Linux networking tools, and an independent verifier. I am thinking of keeping the LLM limited to generating structured intent rather than allowing it to execute commands directly. Does this architecture make sense? Walk through the request flow and point out any weak boundaries or responsibilities I may have assigned incorrectly.

### Prompt 2
> I am thinking of keeping the LLM responsible only for translating natural language into structured tool calls, while the FastMCP server handles policy validation and the network tools perform execution. I believe this makes the LLM non-authoritative. Does this separation make architectural sense, and what security problems does it prevent?

### Prompt 3
> I am considering protecting ports 22, 53, and 5000 from DROP/REJECT operations. My reasoning is that SSH maintains administrative access, DNS is an essential service, and 5000 is used by my own application. Is this a reasonable safety policy, and what failure scenarios does it protect against?

### Prompt 4
> In my current implementation, assistant.py receives the structured tool intent from the LLM and then passes the tool name and arguments to mcp_client.py. The MCP client communicates with my FastMCP server. I am trying to verify that I understand the responsibility split correctly. Should the MCP client only invoke/discover tools while the server remains responsible for policy validation and execution? Trace one firewall request through these components and identify where each decision should happen.

### Prompt 5
> I have implemented my MCP client and FastMCP server as separate components, with the client using stdio transport. I understand the high-level purpose of MCP, but I want to verify what actually travels between the two processes. Explain how the tool name, arguments, request, and response are represented, and distinguish the roles of MCP, JSON-RPC, and stdio in this implementation.

### Prompt 6
> My MCP connection uses JSON-RPC over stdio. I understand that JSON-RPC defines structured requests and responses, but I want to understand exactly what that means in my implementation. Using configure_firewall(port=9999, protocol=tcp, action=DROP) as an example, show what the client is conceptually requesting and what the server returns.

### Prompt 7
> I am using stdio transport between my MCP client and FastMCP server rather than a TCP socket. I initially thought communication between two processes might require a network socket. Explain how stdin/stdout allow the two local processes to exchange MCP messages and contrast this with the TCP socket that my verifier uses for firewall testing.

### Prompt 8
> I have implemented an MCP client and FastMCP server in my project, but I don't have a clear understanding of what MCP actually is. Explain MCP from the basics and then relate the concepts of client, server, tool, request, and response to my network assistant.

### Prompt 9
> I am using iptables in my project, but I don't properly understand how Linux firewalling works. Teach me what iptables is, what tables, chains, rules, matches, and targets mean, and then break down iptables -A INPUT -p tcp --dport 9999 -j DROP step by step.

### Prompt 10
> I am using tc for bandwidth limiting, but I don't understand Linux Traffic Control. Start from the basics: what is tc, what is a qdisc, what is TBF, and what happens when I apply a 10 Mbps limit to eth1?

### Prompt 11
> seeing JSON-RPC in my MCP implementation, but I don't understand what it actually means. Explain JSON-RPC from the very beginning and then show what a request and response would look like when my assistant calls configure_firewall.

### Prompt 12
> I am using BBR in some of my profiles, but I don't fully understand how BBR works. Explain it from the basics, what problem it solves, how it differs from traditional loss-based congestion control, and why it applies to TCP rather than being a generic UDP optimization.

### Prompt 13
> I don't fully understand what happens when a laptop receives a video stream over TCP. Walk me through the path from the remote server to the laptop and explain where receive buffers, congestion control, and queueing can affect the transfer.

### Prompt 14
> I am seeing a bug where a new natural-language request sometimes results in the LLM selecting a tool or arguments similar to a previous request. I suspect conversation history is influencing tool selection. Help me reason through the likely cause and identify exactly where I should inspect the request construction.

### Prompt 15
> I am trying to apply a bandwidth limit to eth1, but my current container only exposes lo and eth0. I need to understand why the test cannot work as intended and what kind of Docker/network setup would provide an appropriate non-protected interface for experimentation.

### Prompt 16
> I have implemented the firewall verifier, but I realize I don't fully understand how a TCP socket actually proves that a firewall DROP rule is working. Explain the TCP connection process from the moment the verifier calls connect(), and then relate each step to what my verifier observes.

### Prompt 17
> I have already built the basic UI for my NetOps MCP Assistant using HTML, CSS, JavaScript, and pywebview. The functionality works, but the interface currently feels more like a developer tool than a polished student project. Review the current layout conceptually and suggest which visual elements I should simplify, enlarge, or reorganize without changing the underlying functionality.

### Prompt 18
> My current interface exposes too many technical implementation details such as “LLM”, “MCP client”, and internal subsystem names. I want the user experience to feel like a normal assistant conversation while still showing useful verification evidence. Suggest how I can present the same information in a more natural conversational UI.

### Prompt 19
> I am considering showing a compact message such as “Processing  5 steps completed” after an operation finishes, with the individual stages hidden until the user expands it. Evaluate whether this is a good UX pattern for my project and suggest what information should remain visible versus collapsible.

### Prompt 20
> I want my UI to show actual Linux command execution evidence when a network operation really executes, but I don't want the interface to look like a terminal emulator. Suggest how I can present the command, stdout/stderr, and exit status in a compact expandable section while keeping the main conversation clean.

### Prompt 21
> I want the UI to show terminal evidence only when an actual backend command was executed. I do not want to generate fake command output just to make the interface look technical. Suggest a clean conditional design for displaying real command evidence and explain what should be shown when an operation is rejected by policy and no command was executed.

### Prompt 22
> whats iptable and what is its components and also when i optimze the proles it should be added to the iptables

### Prompt 23
> okay explain me Never-Drop Ports: 22 (SSH), 53 (DNS), 5000 (UI/Agent)  • Protected Interfaces: eth0, lo (Immune to bandwidth rate-limiting)  • Forbidden Commands: FLUSH_ALL, iptables -F, tc del eth0  • Strict Regex & Range Sanitization (Ports: 1–65535, Rates: 1–100 Mbps) why these are protected and whats the mcp client role checks if the tool exists and then passes to mcp server right

### Prompt 24
> explain me what is mcp and also how does the assitant to mcp and then below works a clear detail with example

### Prompt 25
> okay now i want to propse you a plan fo rthe report i dont know exact structure but i want it this: 1 abstract or introduction or overview or problemstatement or multiple whatever 2) approach 3) architectture section explaining the architecure and how the flow works and everyhtung like that 4) implementations like new features added rollback of the profiles and how they work what firewall rules and all like that 5) verficaction how is it verfied basic level examples or the at what level and all that 6)maybe design of how the ui is designed maybe screenshots if want or not or we can put it in results 7)results here i want to show the graphs of the profiles mainly sho casing it actually being implemented at kernal level or what ever results you say give me a nice overflow

### Prompt 26
> now for the profiles tell me how to test

### Prompt 27
> nl to assistant this acces the llm and gives a structured json by understanding the intent to assistant again and then assistant passes that to mcp and then follows this is the arch i want you yo help me build

### Prompt 28
> okay now what are the valid wonderful easy profies i can show in my project now give me 3

### Prompt 29
> so you are saying it wont work for the youtube

### Prompt 30
> okay so when i use bbc it changes how aggressively the packets comes from youtube server to my laptop when watching video

### Prompt 31
> okay explain me this concept why take iperf3 and how with this cmnds it gets optimized or example, initially: STREAMING PROFILE • congestion control → BBR • queue discipline → FQ • appropriate buffer tuning. These are deterministic settings defined by you, give me a scenerio for streaming and explain me i am not understanding

### Prompt 32
> now after accepting the 9999 even if its not listning port and check connectivity what it should give

### Prompt 33
> but how can i open that and create a new port through cmnds when i ran the compse the whole terminal is like this how can i open docker linux environ

### Prompt 34
> since its linux based did they do docker i mean to show case the presenter whats the best opening vm and running it there or directly windows docker and then docker compose which is the point of mentioning in description and if i have used docker means then it will create linx based kernal in container whcih then be used to apply for that

### Prompt 35
> explain me the architecture in detailed clearly everything

### Prompt 36
> more deeper explanation

### Prompt 37
> give one user ping 8888 first passes to assistant and it gives llm and llm gives back the assistant in json format which will be passed to mcp client and then it passes to server whre it policy checks and and if it passes it will call the netops ping func and runs it in linux environment which then gives the ouput and then verfication subsequently gets called and the output it gaves also saves and then assistant takes these output and passes to the ui

### Prompt 38
> what ports and what ipaddress and what exactly the parameters our application works on

### Prompt 39
> how does the rollback works and also theres usecase right first block and then accepts overrides the block rule which is not how it works in the networking rigjt tell me that

### Prompt 40
> so my docker linux env ipaddress is 127.0.0.1

### Prompt 41
> how backend runs is it on 5000

### Prompt 42
> does it happening i mean when i optimize my gaming is that being added to the iptable rules i didnt check that

### Prompt 43
> running iptables and tc docker rquired granting net_admin and net_raw capabilities to avoid permission denails withou fully comprimising container securiyt

### Prompt 44
>  why is the mcp disconnected

### Prompt 45
> did you apply whats the before and after bandwidth... did it work

### Prompt 46
> tc qdisc show dev eth1 i want to check that the bandwidth limit is being done so i want to check the that with comnd in terminal

### Prompt 47
> for optimization

### Prompt 48
> i think showing the cubic to bbr is enough for testing right

### Prompt 49
> for the iptables tell me

### Prompt 50
> after closingt eh server the rules will get deleted right or after the docker closes or what exactly

### Prompt 51
> okay this is my overall plan: a desktop/web ui in html/css/js that talks to assistant.py, which uses an llm to parse natural language, then calls a fastmcp server over stdio, checks policies.yaml, executes iptables and tc using safe subprocess without shell=True, and verifies with a dual-layer checker. based on this design generate me the initial basic codebase structure with all these components connected.

### Prompt 52
> in llm_client.py i want to integrate groq api instead of running heavy local models because local ollama is taking too long for inference. configure groq with llama-3.3-70b or openai/gpt-oss-120b and pass the exact fastmcp tool json schemas so it outputs clean structured tool calls with name and arguments.

### Prompt 53
> remove the unnecessary files why setup claude when i am just using groq? not even ollama is being used in the final version give me clean llm_client that cleanly talks to groq api with error handling when key is missing or api fails.

### Prompt 54
> in assistant.py make sure if the llm returns an error or is unreachable it doesn't silently execute fallback commands, it should return the error directly to the user and log the step in the timeline.

### Prompt 55
> 1 2 120 DROP tcp -- * * 0.0.0.0/0 0.0.0.0/0 tcp dpt:9999 what cmnd i need to do in terminal to check that it blocked whu the hell is yhat source desti 000
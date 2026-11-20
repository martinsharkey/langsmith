# MCP servers

Client systems reach agents as tools through the Model Context Protocol. `reference/` is a small example used by
the end-to-end test. A real server sits behind the mesh, authenticates its callers and is listed in the agent's
`MCP_SERVERS`; the agent offers the model only the tools named in `MCP_ALLOWED_TOOLS`
(`agents/template/src/innovox_agent/mcp_tools.py`).

# Examples

This section provides examples on how to run SonarQube server in a container:
- using [docker commands](#run-sonarqube-using-docker-commands)
- using [docker-compose](#run-sonarqube-using-docker-compose)

To analyze a project check our [scanner docs](https://docs.sonarqube.org/latest/analysis/overview/).

## Run SonarQube using docker commands
Before you start SonarQube, we recommend creating volumes to store SonarQube data, logs, temporary data and extensions. If you don't do that, you can loose them when you decide to update to newer version of SonarQube or upgrade to a higher SonarQube edition. Commands to create the volumes: 
```bash
$> docker volume create --name sonarqube_data
$> docker volume create --name sonarqube_extensions
$> docker volume create --name sonarqube_logs
$> docker volume create --name sonarqube_temp
``` 

After that you can start the SonarQube server (this example uses the Community Edition):
```bash
$> docker run \
    -v sonarqube_data:/opt/sonarqube/data \
    -v sonarqube_extensions:/opt/sonarqube/extensions \
    -v sonarqube_logs:/opt/sonarqube/logs \
    --name="sonarqube" -p 9000:9000 sonarqube:community
```
The above command starts SonarQube with an embedded database. We recommend starting the instance with a separate database
by providing `SONAR_JDBC_URL`, `SONAR_JDBC_USERNAME` and `SONAR_JDBC_PASSWORD` like this:
```bash
$> docker run \
    -v sonarqube_data:/opt/sonarqube/data \
    -v sonarqube_extensions:/opt/sonarqube/extensions \
    -v sonarqube_logs:/opt/sonarqube/logs \
    -e SONAR_JDBC_URL="..." \
    -e SONAR_JDBC_USERNAME="..." \
    -e SONAR_JDBC_PASSWORD="..." \
    --name="sonarqube" -p 9000:9000 sonarqube:community
```

## Run SonarQube using Docker Compose
### Requirements

 * Docker Engine 20.10+
 * Docker Compose 2.0.0+

### SonarQube with Postgres:

Go to [this directory](example-compose-files/sq-with-h2) to run SonarQube in development mode or [this directory](example-compose-files/sq-with-postgres) to run both SonarQube and PostgreSQL. Then run [docker-compose](https://github.com/docker/compose):

```bash
$ docker-compose up
```

To restart SonarQube container (for example after upgrading or installing a plugin):

```bash
$ docker-compose restart sonarqube
```

## Run SonarQube with MCP Server

The [SonarQube MCP Server](https://github.com/SonarSource/sonarqube-mcp-server) enables AI-powered code analysis through the [Model Context Protocol](https://modelcontextprotocol.io). SonarQube Server (SQS) can be configured to connect to the MCP server at startup.

### Docker Compose (SQS Docker image + MCP)

A reference compose file is available at [example-compose-files/sq-with-mcp-postgres](example-compose-files/sq-with-mcp-postgres). It starts a SonarQube Enterprise instance alongside an MCP server and a PostgreSQL database:

```bash
$ cd example-compose-files/sq-with-mcp-postgres
$ docker-compose up
```

> **Note:** The PostgreSQL database included in this compose file is intended for **testing and evaluation only**. For production deployments, provide your own external database via `SONAR_JDBC_URL`, `SONAR_JDBC_USERNAME`, and `SONAR_JDBC_PASSWORD`.

The compose file sets the following MCP-related environment variables on the SonarQube container:

```yaml
environment:
  SONAR_MCP_ENABLED: "true"
  SONAR_MCP_SERVERURL: "http://mcp:8080"
  SONAR_MCP_HEALTHCHECKINTERVAL: "30"
```

#### SQS MCP environment variables

| Variable | Java property | Description |
|---|---|---|
| `SONAR_MCP_ENABLED` | `sonar.mcp.enabled` | Set to `"true"` to enable the MCP integration. |
| `SONAR_MCP_SERVERURL` | `sonar.mcp.serverUrl` | Full URL of the MCP HTTP endpoint (e.g. `http://mcp:8080`). |
| `SONAR_MCP_HEALTHCHECKINTERVAL` | `sonar.mcp.healthCheck.interval` | How often SQS polls the MCP server health endpoint (e.g. `30s`). |

### Docker Compose (SQS Data Center Edition + MCP)

A reference compose file is available at [example-compose-files/sq-dce-with-mcp-postgres](example-compose-files/sq-dce-with-mcp-postgres). It starts a SonarQube Data Center Edition cluster (two application nodes + three search nodes) alongside an MCP server, an nginx reverse proxy, and a PostgreSQL database:

```bash
$ cd example-compose-files/sq-dce-with-mcp-postgres
$ docker-compose up
```

The two application nodes are not exposed directly; they sit behind an nginx reverse proxy ([`jwilder/nginx-proxy`](https://github.com/nginx-proxy/nginx-proxy)) published on port `80`. The proxy routes requests to the app nodes via the `VIRTUAL_HOST: sonarqube.dev.local` setting, so SonarQube is reachable at `http://sonarqube.dev.local` once that hostname is added to `/etc/hosts`. Both nodes are reachable internally via the `sonarqube` Docker network alias, which is what the MCP server uses to connect (`http://sonarqube:9000`).

> **Note:** The PostgreSQL database included in this compose file is intended for **testing and evaluation only**. For production deployments, provide your own external database via `SONAR_JDBC_URL`, `SONAR_JDBC_USERNAME`, and `SONAR_JDBC_PASSWORD`.

### Connecting an MCP client (e.g. Claude)

Once SonarQube and the MCP server are running, you need a **user token** to authenticate MCP requests.

**1. Generate a user token in SonarQube:**

Go to **My Account → Security → Generate Token** in the SonarQube UI (`http://localhost:9000`), create a token of type *User Token*, and copy the value.

**2. Add the MCP server to your Claude configuration:**

Add the `sonarqube` entry under `mcpServers` in your Claude configuration file:
- Claude Code (CLI): `~/.claude.json`
- Claude Desktop (app): `claude_desktop_config.json` (typically `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS)

```json
{
  "mcpServers": {
    "sonarqube": {
      "type": "http",
      // SonarQube Server (SQS) proxies MCP requests via the /mcp endpoint. (In this example, http://localhost:9000/mcp)
      "url": "${SONARQUBE_URL}/mcp",
      "headers": {
        "Authorization": "Bearer <your-user-token>"
      }
    }
  }
}
```

Replace `<your-user-token>` with the token generated in the previous step. Restart Claude after saving the configuration.
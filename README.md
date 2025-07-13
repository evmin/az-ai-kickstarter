# AI Applications Chassis - AI Apps Best Practices Tailored for Azure

ToC: [**USER STORY**](#azure-ai-app-kickstarter) \| [**GETTING STARTED**](#getting-started)  \| [**HOW IT WORKS**](#how-it-works)

## Azure AI App Kickstarter

An opinionated set of best practices and patterns to bootstrap your Multi Agent application in minutes.

#### Architechture

<img src="doc/images/arch-infra.png" alt="High level Kickstarter architecture - infra view" width="800">

#### Architecture Description

Application is using **[Chainlit](https://docs.chainlit.io/)** as the frontend framework and relies on **[Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/overview/)** for the cognitive architecture.

The two ways to use the application:

* Chat with an agent defined in **[AI Foundry Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/overview)**
* Chat with multi agent **Debate** pattern defined within Semantic Kernel

### Debate Pattern Architecture

<img src="doc/images/arch-app.png" alt="Kickstarter cognitive architecture - app view" width="800">

This architecture implements a **Debate Pattern** using the **[Semantic Kernel's](https://learn.microsoft.com/en-us/semantic-kernel/overview/) [agent framework](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/?pivots=programming-language-python)**, a dynamic environment where multiple AI agents collaborate to refine ideas, test arguments, or reach a resolution.

The core architecture components based on Semantic Kernel abstractions:

   - **Speaker Selection Strategy** (Green Box):
     - This component determines which agent (WRITER or CRITIC) "speaks" next.
     - It ensures productive collaboration by regulating the flow of interaction between the agents and preventing redundant actions.
   - **WRITER Agent**: provides the initial proposal and the subsequent revisions following the direction from critic.
   - **CRITIC Agent**: evaluates the text and provides constructive feedback to drive readibility and popularity of the post. Provides scoring across a number of categories and a final score.
   - **Chat Termination Strategy** (Red Box):
     - This component decides when the conversation has reached a satisfactory conclusion. It takes the overall critic score and compares to acceptance treshold. 

Semantic Kernel powers the agents with features like prompt engineering, memory recall, and logic orchestration.

## Getting Started

### Codespaces and DevContainers

This respository has been configured to support GitHub Codespace and DevContainers.
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/evmin/az-ai-kickstarter) [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/evmin/az-ai-kickstarter)

> [!WARNING]
> **DO NOT** `git clone` the application under Windows and then open a DevContainer. This would create issues with file end of lines. 
> 
> **For DevContainer** click on the button above and let Visual Studio Code download the repository for you. 
> 
> Alternatively you can also `git clone` under **Windows Subsystem for Linux** (WSL) and ask Visual Studio Code to`Re-Open in Container`.

### Dependencies

  - [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/what-is-azure-cli): `az`
  - [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/overview): `azd`
  - [Python](https://www.python.org/about/gettingstarted/): `python`
  - [UV](https://docs.astral.sh/uv/getting-started/installation/): `uv`
  - Optionally [Docker](https://www.docker.com/get-started/): `docker` 

See below for installation instructions

### Quick deploy

[Dependency Install Guide](doc/DEPENDENCY_INSTALL.md)

#### Customizing the deployment

See [infra/README.md](infra/README.md) for instructions about how to 
customize the deployment 

#### Deploy 

To deploy Azure AI App Kickstarter just run: 
```bash
azd up
```
> [!WARNING]
> This deploys the application with authentication DISABLED.

## How it works

### Running locally

```bash
cd src/frontend
uv sync
uv run chainlit run app.py -w
```

### Tracing

The AI Traces you will be able to find in AI Foundry Project under "Tracing".
If you click on one of the traces you will see a detailed history view with every agent, prompt, etc. 

For example, Debate Pattern tracing:

<img src="doc/images/tracing.png" alt="Azure AI Foundry Portal Trace Detail" width="800">

### Accessing logs of Azure Container Apps

Use `az containerapp logs` (or the Azure Portal) to inspect logs of the deployed Container App. 

Example:

```bash
eval $(azd env get-values)
az containerapp logs show \
   --name ca-frontend-$AZURE_ENV_NAME \
   --resource-group $AZURE_RESOURCE_GROUP \
   --follow
```

<img src="doc/images/logging.png" alt="Azure AI Foundry Portal Trace Detail" width="800">

## Code of Conduct

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).

Resources:

- [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/)
- [Microsoft Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/)
- Contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with questions or concerns

For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Responsible AI Guidelines

This project follows the below responsible AI guidelines and best practices, please review them before using this project:

- [Microsoft Responsible AI Guidelines](https://www.microsoft.com/en-us/ai/responsible-ai)
- [Responsible AI practices for Azure OpenAI models](https://learn.microsoft.com/en-us/legal/cognitive-services/openai/overview)
- [Safety evaluations transparency notes](https://learn.microsoft.com/en-us/azure/ai-studio/concepts/safety-evaluations-transparency-note)

## Acknowledgements

  * Kudos to [Pamela Fox](https://github.com/pamelafox) and [James Casey](https://github.com/jamesc) for [Azure-Samples/openai-chat-app-entra-auth-builtin](https://github.com/Azure-Samples/openai-chat-app-entra-auth-builtin) from which we borrowed most of authentication & authorization setup.
  * Special thank you to [Michael Hofer](https://github.com/mhofer1976) for extensive testing and solving o1 compatibility

## Authors

  * [Dominique Broeglin](https://github.com/dbroeglin)
  * [Evgeny Minkevich](https://github.com/evmin)

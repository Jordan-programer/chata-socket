# Suite de Telemetria de Sockets: TCP vs UDP (Chat & Benchmark)

Este repositório contém um projeto completo desenvolvido para a disciplina de **Sistemas Distribuídos**, focado no desenvolvimento, teste de estresse e análise comparativa de desempenho entre os protocolos de transporte **TCP** e **UDP**.

O projeto traz um núcleo robusto de sockets puros em **Python 3** acoplado a um **Dashboard Web interativo ultra-premium** (HTML5, CSS3, Vanilla JS e Chart.js) projetado sob os conceitos mais modernos de design (Glassmorphic Dark Theme) e configurado para coletar dados em tempo real e compilar automaticamente relatórios acadêmicos formatados para impressão em A4/PDF!

---

## 💥 Parâmetros Comparados
* **Tempo de Entrega (Latency / RTT)**: Coleta precisa em microssegundos (`time.perf_counter`) entre o envio e o recebimento de echos.
* **Perda de Mensagens (Packet Loss Rate)**: Razão estatística de pacotes transmitidos que falharam em retornar.
* **Uso de CPU & RAM**: Monitoramento ativo em segundo plano dos processos de socket locais via framework `psutil`.
* **Ordem de Entrega (Ordering)**: Verificação de inversões na chegada de números de sequência (sequence IDs) nos pacotes.

---

## 📁 Estrutura do Projeto
* `tcp_server.py` e `tcp_client.py`: Chat persistente em socket TCP clássico com multiplexação por threads.
* `udp_server.py` e `udp_client.py`: Chat connectionless em socket UDP clássico com suporte a simulação programável de perda de pacotes.
* `benchmark_orchestrator.py`: Engine de teste estatístico de alta resolução. Dispara instâncias dos servidores em subprocessos isolados, gerencia conexões e monitora telemetria de hardware.
* `web_dashboard_server.py`: Servidor HTTP assíncrono que une todas as pontas expostas em endpoints JSON de controle.
* `dashboard/`:
  * `index.html`: Estrutura do painel de controle de benchmarks, console de log e áreas de chat.
  * `style.css`: Estilização translúcida (glassmorphism), efeitos neon e folhas de estilo otimizadas para impressão.
  * `app.js`: Coordenação de telemetria, gráficos interativos Chart.js, chat interativo de microsegundos e compilação do artigo científico.

---

## 🛠️ Requisitos de Instalação
O projeto utiliza bibliotecas nativas do Python 3, requerendo apenas o módulo `psutil` para a captura de métricas do processador e memória física.

No terminal, instale o requisito:
```bash
pip install psutil
```

---

## 🚀 Como Executar o Projeto

Existem duas formas complementares de usar esta suite: **Modo Dashboard Web (Recomendado)** e **Modo CLI Tradicional**.

### Método 1: Modo Dashboard Web (Completo & Gráfico)

Este é o modo ideal para apresentar o trabalho acadêmico. Ele ativa os servidores e expõe a interface gráfica completa.

1. **Inicie o Servidor do Dashboard**:
   Abra um terminal na pasta do projeto e execute:
   ```bash
   python web_dashboard_server.py
   ```
   *O console indicará que o servidor está rodando no endereço `http://localhost:8000`.*

2. **Inicie os Servidores de Chat Interativos** (Opcional, para a aba "Chat Interativo"):
   Abra dois novos terminais adicionais e inicialize os servidores nas portas padrão:
   * **Servidor TCP** (Terminal 2):
     ```bash
     python tcp_server.py
     ```
   * **Servidor UDP** (Terminal 3):
     ```bash
     python udp_server.py
     ```

3. **Acesse no seu Navegador**:
   Abra seu navegador de preferência e acesse:
   👉 **[http://localhost:8000](http://localhost:8000)**

---

### Método 2: Modo CLI Tradicional (Terminais de Chat)

Se preferir testar apenas o fluxo clássico dos chats em linha de comando como uma demonstração crua de sockets:

1. **Inicie os Servidores** em terminais separados:
   ```bash
   python tcp_server.py
   ```
   ```bash
   python udp_server.py
   ```

2. **Inicie os Clientes** em novos terminais:
   * Para chat TCP:
     ```bash
     python tcp_client.py
     ```
   * Para chat UDP:
     ```bash
     python udp_client.py
     ```
   *Digite um nome de usuário e envie mensagens diretamente pelo prompt!*

---

## 📊 O Painel de Telemetria e Benchmark Web

Ao abrir o dashboard web, você poderá configurar cenários de estresse científico:
1. **Quantidade de mensagens**: Altere de 100 até 10.000 pacotes.
2. **Intervalo entre Msgs (ms)**: Defina a frequência. Ajuste para **0ms** para gerar rajadas massivas de estresse (Stress Burst).
3. **Simulador de Perda UDP**: Ajuste o slider para simular, por exemplo, 15% ou 30% de perda artificial no transporte UDP para evidenciar a instabilidade inerente do protocolo contra a integridade estrita do TCP.
4. **Relatório Automático**: Após os testes, navegue até a aba **Relatório Acadêmico** para ver um artigo pré-formatado nos moldes propostos pelo professor, contendo suas estatísticas reais, tabelas e parágrafos de descobertas científicas preenchidos de forma dinâmica. **Pressione `Ctrl + P` ou clique no botão Imprimir para salvar o arquivo em formato PDF com a formatação Times New Roman acadêmica limpa.**

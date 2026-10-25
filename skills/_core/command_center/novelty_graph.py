"""3D Semantic Knowledge Graph for the MONEEG Scientific Manuscript.

Visualizes the core novelty, state-of-the-art gaps, embedded hardware pillars,
empirical thesis evidence, Elsevier manuscript sections, and crucially the
8 core narrative pillars of the paper:
1. Aplicaciones de interés (TDAH, neurofeedback, serious games)
2. Problema central del paper (Jitter temporal en SOs, piso de ruido >5 µVpp, ergonomía pediátrica)
3. Las 5 ideas más cercanas del Estado del Arte (BEATS, LSL, OpenBCI Daisy, Cascos consumo, VR Oddball)
4. La novedad que se vende con sus 2 a 3 ítems clave (Sincronía <5 µs, Front-End 32-Ch <1.1 µVpp, Inyección en cabecera)
5. Los datasets probados (Banco de calibración 32-ch, Dataset P300 tesis Julián, Ensayo 400 min / 250 Hz)
6. Las medidas de desempeño y métodos a comparar (Jitter µs vs ms, Piso de ruido µVpp, Pérdida de paquetes vs OpenBCI & Clínicos)
7. Las 3 conclusiones más fuertes de los resultados (Preservación P300 >40%, Calidad clínica abierta, 0% pérdida en 400 min)
8. Las 2 a 3 líneas de trabajo futuro más relevantes (Edge ICA/CSP, Ensayo multicéntrico TDAH, Wireless determinista)
"""

from __future__ import annotations

import json
from typing import Any

NOVELTY_GRAPH_DATA: dict[str, Any] = {
    "title": "Grafo 3D de Novedad e Ideas del Manuscrito MONEEG",
    "target_journal": "Elsevier Biomedical Signal Processing and Control",
    "authors": "Julián David Parias Osorio & Andrés Álvarez",
    "project": "Minciencias-92056",
    "summary": "Mapeo topológico de los 8 pilares narrativos del artículo MONEEG: aplicaciones, problemas, SOTA, novedades clave, datasets, métricas comparativas, conclusiones y trabajo futuro.",
    "nodes": [
        # =====================================================================
        # 0. NODO CENTRAL / SÍNTESIS GLOBAL (CYAN)
        # =====================================================================
        {
            "id": "core-moneeg",
            "label": "MONEEG: Open-Access 32-Ch BCI",
            "group": "core",
            "color": "#38bdf8",
            "size": 9.0,
            "category": "Contribución Global",
            "badge": "ARQUITECTURA PRINCIPAL",
            "desc": "Framework embebido de adquisición de EEG de 32 canales con sincronización hardware determinista (<5 µs) y piso de ruido submicrovoltio (<1.1 µVpp) optimizado para monitoreo cognitivo pediátrico.",
            "rhetorical_question": "¿Cuál es la contribución técnica y traslacional definitiva que introduce el artículo frente a los sistemas BCI existentes?",
            "paragraph_text": "MONEEG resolves this bottleneck through a co-designed embedded architecture. By combining a bare-metal 120 MHz ARM Cortex-M4F microcontroller with four cascaded ADS1299 analog front-ends, the platform performs synchronized 24-bit delta-sigma conversion across 32 channels, embedding serious game stimulus trigger flags directly into the SPI transmission frame at the hardware interrupt level.",
            "metrics": "32 Canales, 24 bits, ADC Σ-Δ, 250 Hz, <1.1 µVpp, latencia <5 µs, 0% pérdida en 400 min.",
            "novelty_claim": "Supera la disyuntiva entre amplificadores clínicos inaccesibles/pesados y cascos comerciales ruidosos con jitter temporal severo.",
            "thesis_ref": "Capítulo 3 (Diseño Hardware y Firmware), Tesis J. Parias",
            "pdf_page": 2,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["title-and-keywords.title", "abstract.slot-3", "introduction.block-3"]
        },

        # =====================================================================
        # 1. APLICACIONES DE INTERÉS (SKY BLUE)
        # =====================================================================
        {
            "id": "app-hub",
            "label": "1. Aplicaciones de Interés Clínico",
            "group": "app",
            "color": "#0ea5e9",
            "size": 7.0,
            "category": "Aplicaciones de Interés",
            "badge": "DIMENSIÓN 1 / TRASLACIÓN",
            "desc": "Áreas clínicas y tecnológicas prioritarias donde MONEEG aporta valor diagnóstico, terapéutico y experimental.",
            "rhetorical_question": "¿En qué contextos clínicos y de neurorrehabilitación se proyecta el despliegue del sistema?",
            "paragraph_text": "Pediatric neurodevelopmental disorders, particularly Attention Deficit Hyperactivity Disorder (ADHD), place severe demands on clinical assessment and rehabilitation tools. Conventional systems fail to combine child-friendly ergonomics with high temporal precision.",
            "metrics": "Población pediátrica 6–14 años, entornos escolares y clínicos.",
            "novelty_claim": "Habilita la evaluación objetiva de biomarcadores en niños sin fatiga ni rechazo conductual.",
            "thesis_ref": "Capítulo 1 (Justificación y Alcance)",
            "pdf_page": 1,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["abstract.slot-1", "introduction.block-1"]
        },
        {
            "id": "app-adhd",
            "label": "Monitoreo Cognitivo en TDAH",
            "group": "app",
            "color": "#0ea5e9",
            "size": 5.0,
            "category": "Aplicaciones de Interés",
            "badge": "POBLACIÓN CLÍNICA",
            "desc": "Diagnóstico objetivo y seguimiento neurofisiológico en infantes con déficit de atención e hiperactividad.",
            "rhetorical_question": "¿Por qué el TDAH requiere una plataforma de registro con sincronización de estímulos a nivel de microsegundo?",
            "paragraph_text": "Children with ADHD exhibit transient deficits in attentional orienting and inhibitory control, reflected in low-amplitude ERP markers (P300 and N200) that require precise single-trial phase alignment to prevent diagnostic misclassification.",
            "metrics": "Prevalencia global del 5–7% en edad escolar; modulación de onda P300 atencional.",
            "novelty_claim": "Proporciona fidelidad clínica en un formato ergonómico de rápida colocación.",
            "thesis_ref": "Capítulo 1 (Sección 1.1: Problemática del TDAH en Colombia)",
            "pdf_page": 1,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["introduction.block-1", "abstract.slot-1"]
        },
        {
            "id": "app-neurofeedback",
            "label": "Neurorrehabilitación por Neurofeedback",
            "group": "app",
            "color": "#0ea5e9",
            "size": 4.8,
            "category": "Aplicaciones de Interés",
            "badge": "TERAPIA DIGITAL",
            "desc": "Entrenamiento de autorregulación electrofisiológica mediante retroalimentación de ritmos corticales (SMR, Theta/Beta).",
            "rhetorical_question": "¿Cómo apoya la plataforma las sesiones continuas de entrenamiento neurocognitivo?",
            "paragraph_text": "Therapeutic neurofeedback protocols require sustained streaming stability and immediate feedback loops without signal latency or packet jitter that disrupt operant conditioning.",
            "metrics": "Sesiones de 30–45 minutos, latencia de feedback de bucle cerrado < 100 ms.",
            "novelty_claim": "Streaming continuo y robusto con cero pérdida de paquetes durante sesiones terapéuticas completas.",
            "thesis_ref": "Capítulo 1 (Sección 1.2: Antecedentes de Neurofeedback)",
            "pdf_page": 2,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["introduction.block-2", "conclusions.concl-block-4"]
        },
        {
            "id": "app-serious-games",
            "label": "Interacción con Videojuegos Serios ('Eagle Eye')",
            "group": "app",
            "color": "#0ea5e9",
            "size": 5.0,
            "category": "Aplicaciones de Interés",
            "badge": "ENTORNO LÚDICO",
            "desc": "Integración nativa con videojuegos serios en Unity para entrenar atención sostenida y control inhibitorio en infantes.",
            "rhetorical_question": "¿Cómo se vincula la dinámica lúdica del videojuego con el hardware de digitalización cerebral?",
            "paragraph_text": "Stimulus render events from the Unity serious game Eagle Eye trigger a physical interrupt that latches marker codes into the SPI frame header at the exact instant of ADC sampling, enabling seamless ERP paradigms in children.",
            "metrics": "Disparos Go/No-Go sincronizados a nivel de microsegundo con la GPU/pantalla.",
            "novelty_claim": "Erradica la desconexión temporal entre el motor del juego y el flujo de telemetría biopotencial.",
            "thesis_ref": "Capítulo 3 (Sección 3.6: Integración con Videojuego Serio), pág. 60",
            "pdf_page": 5,
            "section_ref": "Sección 3 (Materiales y Métodos)",
            "paper_blocks": ["introduction.block-3", "materials-and-methods.mm-proposal"]
        },

        # =====================================================================
        # 2. PROBLEMA CENTRAL DEL PAPER (ROSE / CRIMSON)
        # =====================================================================
        {
            "id": "problem-hub",
            "label": "2. Problema Central del Paper",
            "group": "problem",
            "color": "#f43f5e",
            "size": 7.0,
            "category": "Problema Central",
            "badge": "DIMENSIÓN 2 / CUELLOS DE BOTELLA",
            "desc": "La triada de limitaciones críticas en sistemas BCI abiertos: dispersión temporal aleatoria, ruido analógico y desajuste ergonómico.",
            "rhetorical_question": "¿Cuál es la barrera metodológica fundamental que impide usar dispositivos abiertos actuales en entornos pediátricos?",
            "paragraph_text": "The survey revealed a persistent technical gap: in available open-source architectures, event markers are transmitted via asynchronous software protocols, introducing stochastic operating system delays (10--50 ms) that corrupt phase alignment in ERP extraction.",
            "metrics": "Atenuación del P300 >40% por jitter; ruido >5 µVpp en hardware de bajo costo.",
            "novelty_claim": "Formaliza las razones por las cuales el timestamping por software destruye la fidelidad diagnóstica de los potenciales evocados.",
            "thesis_ref": "Capítulo 2 (Marco Teórico y Estado del Arte), pág. 24",
            "pdf_page": 1,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["abstract.slot-2", "introduction.block-2"]
        },
        {
            "id": "prob-jitter",
            "label": "Jitter Temporal en SOs (10–50 ms)",
            "group": "problem",
            "color": "#f43f5e",
            "size": 5.2,
            "category": "Problema Central",
            "badge": "BOTELLA CRÍTICA",
            "desc": "En stacks convencionales (LSL, sockets UDP en Windows/Linux), la latencia variable de buffering destruye la coherencia de fase ERP.",
            "rhetorical_question": "¿Por qué el buffering del sistema operativo destruye la forma de onda de los potenciales evocados?",
            "paragraph_text": "When stimulus delivery software and data acquisition software run on separate execution loops, network and OS buffering produce random temporal jitter exceeding 30 ms. In ERP averaging, a jitter of this magnitude completely blurs high-frequency components and attenuates the P300 amplitude by more than 40%.",
            "metrics": "Dispersión 18.5 ± 6.2 ms en sockets de SO vs <5 µs en interrupción hardware.",
            "novelty_claim": "Justifica matemáticamente la necesidad ineludible de inyección de marcas en hardware bare-metal.",
            "thesis_ref": "Capítulo 2 (Marco Teórico y Estado del Arte), pág. 28",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["introduction.block-2", "related-work.rw-problem-blocks"]
        },
        {
            "id": "prob-noise",
            "label": "Piso de Ruido Elevado en Hardware Abierto (>5 µVpp)",
            "group": "problem",
            "color": "#f43f5e",
            "size": 5.0,
            "category": "Problema Central",
            "badge": "BOTELLA ANALÓGICA",
            "desc": "Dispositivos accesibles y cascos comerciales carecen de front-ends analógicos de precisión y planos de masa aislados.",
            "rhetorical_question": "¿Qué limita la detección de microvoltios sutiles en dispositivos electroencefalográficos económicos?",
            "paragraph_text": "Furthermore, analog noise floors often exceed 5 µVpp in low-cost headsets, washing out low-amplitude microvolt cortical responses and preventing reliable extraction of single-trial neurocognitive markers.",
            "metrics": "Ruido >5 µVpp en consumo (OpenBCI daisy: ~1.5 µVpp; EEGNet MCU: ~3.0 µVpp).",
            "novelty_claim": "MONEEG garantiza <1.1 µVpp con Sigma = 0.14 µV en sus 32 canales.",
            "thesis_ref": "Capítulo 4 (Resultados de Banco de Pruebas), pág. 62",
            "pdf_page": 1,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["abstract.slot-2", "introduction.block-2"]
        },
        {
            "id": "prob-ergonomics",
            "label": "Ergonomía Pediátrica Inadecuada",
            "group": "problem",
            "color": "#f43f5e",
            "size": 4.6,
            "category": "Problema Central",
            "badge": "BOTELLA MECÁNICA",
            "desc": "Gorros clínicos estándar para adultos con cables pesados a torres generan aversión, ansiedad y artefactos de movimiento en niños.",
            "rhetorical_question": "¿Por qué los montajes clínicos convencionales fallan en pacientes pediátricos durante sesiones de juego?",
            "paragraph_text": "Standard clinical setups rely on rigid, high-density caps connected via cumbersome tethers to expensive benchtop amplifiers, causing anxiety and behavioral resistance in young subjects. Conversely, low-cost consumer headsets lack channel density and exhibit excessive inter-electrode impedance variance.",
            "metrics": "Circunferencias adultas 56–58 cm no ajustables a 50–54 cm pediátrico.",
            "novelty_claim": "Casco modular flexible 3D liviano (<220 g) con monturas articuladas para electrodos pediátricos.",
            "thesis_ref": "Capítulo 3 (Diseño Mecánico y Ensamble 3D), pág. 45",
            "pdf_page": 2,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["introduction.block-1", "materials-and-methods.mm-proposal"]
        },

        # =====================================================================
        # 3. LAS 5 IDEAS MÁS CERCANAS DEL SOTA (CORAL / ROSE)
        # =====================================================================
        {
            "id": "sota-hub",
            "label": "3. 5 Ideas Más Cercanas del SOTA",
            "group": "sota",
            "color": "#fb7185",
            "size": 7.0,
            "category": "Estado del Arte",
            "badge": "DIMENSIÓN 3 / BENCHMARKS",
            "desc": "Los 5 referentes tecnológicos más próximos en la literatura de hardware abierto, streaming y BCI lúdico.",
            "rhetorical_question": "¿Qué marcos de trabajo contemporáneos representan la vanguardia más próxima y cuáles son sus límites?",
            "paragraph_text": "Our exploratory 3D atlas compilation of 18 peer-reviewed neurotechnology frameworks confirms that MONEEG occupies a unique quadrant: multi-channel research-grade biopotential precision combined with deterministic stimulus synchronization and pediatric ergonomics.",
            "metrics": "18 sistemas auditados, 4 familias taxonómicas, ventana temporal 2020–2025.",
            "novelty_claim": "Posiciona el manuscrito mediante comparación objetiva y metrológica.",
            "thesis_ref": "Capítulo 2 (Marco Teórico y Estado del Arte de la Tesis)",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-preamble", "related-work.rw-panorama"]
        },
        {
            "id": "sota-beats",
            "label": "1. BEATS (IEEE TBCAS 2022)",
            "group": "sota",
            "color": "#fb7185",
            "size": 4.8,
            "category": "Estado del Arte",
            "badge": "REFERENTE HW ABIERTO",
            "desc": "Sistema abierto multicanal de adquisición biopotencial; hito pionero en hardware libre con ADS1299.",
            "rhetorical_question": "¿Por qué la arquitectura mononúcleo de BEATS es vulnerable bajo tráfico de red intenso?",
            "paragraph_text": "Among open-source systems, BEATS represents a notable milestone; however, it utilizes a single-MCU architecture where high-throughput Wi-Fi socket handling can preempt critical time-sensitive ADC servicing under peak network load, leading to unhandled packet drops.",
            "metrics": "16 canales, arquitectura de microcontrolador mononúcleo.",
            "novelty_claim": "MONEEG desacopla la conversión ADC con interrupción determinista y DMA circular prioritario.",
            "thesis_ref": "Capítulo 2 (Sección 2.3: Sistemas de Hardware Abierto)",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-panorama", "materials-and-methods.mm-borrowed-machinery"]
        },
        {
            "id": "sota-lsl",
            "label": "2. Lab Streaming Layer (LSL)",
            "group": "sota",
            "color": "#fb7185",
            "size": 4.8,
            "category": "Estado del Arte",
            "badge": "REFERENTE STREAMING",
            "desc": "Protocolo de facto por software para sincronización multimodal en neurociencias sobre redes locales.",
            "rhetorical_question": "¿Por qué el enfoque de software de LSL no resuelve el jitter en paradigmas de microsegundos?",
            "paragraph_text": "While LSL is widely adopted for laboratory integration, its software-based timestamping relies on OS scheduling clocks subject to network stack latency and thread context switching, introducing 10--50 ms variance.",
            "metrics": "Jitter medido: 18.5 ± 6.2 ms en sockets UDP de SO.",
            "novelty_claim": "MONEEG estampa el evento en la cabecera SPI en 2.4 µs, erradicando el desfase de LSL.",
            "thesis_ref": "Capítulo 2 (Sección 2.4: Protocolos de Sincronización Temporal)",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-problem-blocks", "results-and-discussion.rd-contribution-blocks"]
        },
        {
            "id": "sota-openbci",
            "label": "3. OpenBCI Cyton + Daisy (16 Ch)",
            "group": "sota",
            "color": "#fb7185",
            "size": 4.8,
            "category": "Estado del Arte",
            "badge": "REFERENTE COMERCIAL ABIERTO",
            "desc": "Plataforma de código abierto de 16 canales ampliamente usada en la comunidad BCI aficionada y académica.",
            "rhetorical_question": "¿Qué limitaciones técnicas presenta OpenBCI al escalar a 32 canales y sincronía estricta?",
            "paragraph_text": "OpenBCI provides accessible EEG acquisition but caps at 16 channels via its daisy add-on board, introducing SPI communication skew between boards, a noise floor near 1.5 µVpp, and no integrated pediatric mechanical frame.",
            "metrics": "16 canales máx, ~1.5 µVpp de piso de ruido, sincronía no determinista.",
            "novelty_claim": "MONEEG entrega 32 canales sincrónicos en una sola placa con ruido <1.1 µVpp y sincronía <5 µs.",
            "thesis_ref": "Capítulo 2 (Sección 2.3: Análisis Comparativo de OpenBCI)",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-panorama", "results-and-discussion.rd-general-task"]
        },
        {
            "id": "sota-consumer",
            "label": "4. Cascos Comerciales de Consumo (Emotiv / Muse)",
            "group": "sota",
            "color": "#fb7185",
            "size": 4.5,
            "category": "Estado del Arte",
            "badge": "DISPOSITIVOS DE CONSUMO",
            "desc": "Sistemas de electrodos secos orientados a bienestar mental, videojuegos y aplicaciones recreativas.",
            "rhetorical_question": "¿Por qué los dispositivos de consumo carecen de validez diagnóstica en neurodesarrollo?",
            "paragraph_text": "Consumer headsets such as Emotiv and Muse provide plug-and-play operation but lack channel density (4--14 channels), suffer from excessive electrode impedance fluctuation, and lack open trigger interfaces for ERP extraction.",
            "metrics": "4–14 canales, impedancia inestable >50 kΩ, protocolos cerrados y propietarios.",
            "novelty_claim": "MONEEG combina la facilidad de colocación de cascos ligeros con rigor clínico de 32 canales.",
            "thesis_ref": "Capítulo 2 (Sección 2.2: Dispositivos de Consumo vs Clínicos)",
            "pdf_page": 3,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-panorama", "introduction.block-1"]
        },
        {
            "id": "sota-vr-oddball",
            "label": "5. Tareas VR & Serious Games Oddball ERP",
            "group": "sota",
            "color": "#fb7185",
            "size": 4.5,
            "category": "Estado del Arte",
            "badge": "PARADIGMAS COGNITIVOS",
            "desc": "Estudios recientes de estimulación lúdica (Frontiers in Neurorobotics 2022, JMIR Serious Games 2024).",
            "rhetorical_question": "¿Cuál es la desconexión común entre el motor gráfico de estímulos y el equipo de registro?",
            "paragraph_text": "Recent literature explores gamified Oddball paradigms in virtual environments for ADHD evaluation, yet virtually all implementations rely on offline post-hoc alignment or loose network timestamps.",
            "metrics": "Desfase estímulo-respuesta variable entre 10 y 60 ms en motores gráficos.",
            "novelty_claim": "MONEEG establece enlace físico por interrupción de hardware con el motor gráfico Unity.",
            "thesis_ref": "Capítulo 2 (Sección 2.5: Videojuegos y Potenciales Evocados)",
            "pdf_page": 4,
            "section_ref": "Sección 2 (Related Work)",
            "paper_blocks": ["related-work.rw-synthesis-artefact", "materials-and-methods.mm-proposal"]
        },

        # =====================================================================
        # 4. LA NOVEDAD QUE SE PRETENDE VENDER (3 ÍTEMS CLAVE) (EMERALD)
        # =====================================================================
        {
            "id": "novelty-hub",
            "label": "4. Novedad Central (3 Pilares Clave)",
            "group": "novelty",
            "color": "#10b981",
            "size": 7.0,
            "category": "Novedad Central",
            "badge": "DIMENSIÓN 4 / NÚCLEO CIENTÍFICO",
            "desc": "Los tres pilares de ingeniería de co-diseño que sustentan la novedad vendida a Elsevier BSPC.",
            "rhetorical_question": "¿Cuáles son los 3 avances técnicos diferenciales que MONEEG introduce y valida empíricamente?",
            "paragraph_text": "The core novelty of MONEEG is articulated around three architectural innovations: deterministic hardware synchronization (<5 µs), a cascaded 32-channel submicrovolt AFE array (<1.1 µVpp), and direct trigger embedding in the SPI protocol frame.",
            "metrics": "Latencia <5 µs, Ruido <1.1 µVpp, 32 canales síncronos a 250 Hz.",
            "novelty_claim": "Constituye la defensa central del artículo frente a los revisores internacionales.",
            "thesis_ref": "Capítulo 3 (Diseño Hardware y Firmware de MONEEG)",
            "pdf_page": 2,
            "section_ref": "Sección 1 (Introducción)",
            "paper_blocks": ["abstract.slot-3", "introduction.block-3", "conclusions.concl-block-1"]
        },
        {
            "id": "nov-sync",
            "label": "Pilar 1: Sincronía Hardware Determinista (<5 µs)",
            "group": "novelty",
            "color": "#10b981",
            "size": 5.4,
            "category": "Novedad Central",
            "badge": "NOVEDAD CLAVE 1",
            "desc": "Interrupción externa GPIO en ARM Cortex-M4F bare-metal que engancha flags de estímulo en la trama SPI en <5 µs.",
            "rhetorical_question": "¿Cómo se logra sincronización temporal a nivel de microsegundos sin retardos de buffers de SO?",
            "paragraph_text": "By executing on a bare-metal 120 MHz ARM Cortex-M4F microcontroller without general-purpose OS layers, task dispatching is strictly governed by deterministic hardware interrupts, ensuring ISR latency under 1 microsecond.",
            "metrics": "2.4 µs de latencia media, dispersión estándar σ = 0.35 µs (>7,000x más preciso que LSL).",
            "novelty_claim": "Erradica el jitter temporal en el origen físico de la digitalización.",
            "thesis_ref": "Capítulo 3 (Sección 3.4: Sincronización Temporal de Eventos), pág. 55",
            "pdf_page": 5,
            "section_ref": "Sección 3 (Materiales y Métodos)",
            "paper_blocks": ["abstract.slot-4", "abstract.slot-6", "introduction.block-3"]
        },
        {
            "id": "nov-afe",
            "label": "Pilar 2: Front-End 32-Ch Submicrovoltio (<1.1 µVpp)",
            "group": "novelty",
            "color": "#10b981",
            "size": 5.4,
            "category": "Novedad Central",
            "badge": "NOVEDAD CLAVE 2",
            "desc": "Arreglo en cascada daisy-chain de 4x ADS1299 con aislamiento galvánico y planos de masa analógico/digital en estrella.",
            "rhetorical_question": "¿Cómo se adquieren 32 canales simultáneos de 24 bits con piso de ruido inferior a un microvoltio?",
            "paragraph_text": "The biopotential acquisition front-end consists of four Texas Instruments ADS1299 ICs in a SPI daisy-chain configuration. Cascaded SPI allows reading all 32 channels (96 bytes plus status words) in a single synchronous DMA transaction triggered by DRDY.",
            "metrics": "32 CH, Vpp < 1.1 µV (media 0.94 µV, σ = 0.14 µV), CMRR > 110 dB.",
            "novelty_claim": "Iguala la pureza de señal de amplificadores clínicos comerciales a una fracción del costo.",
            "thesis_ref": "Capítulo 3 (Sección 3.2: Arreglo de Front-Ends Analógicos), Fig. 3.4",
            "pdf_page": 4,
            "section_ref": "Sección 3 (Materiales y Métodos)",
            "paper_blocks": ["abstract.slot-4", "materials-and-methods.mm-borrowed-machinery"]
        },
        {
            "id": "nov-trigger-embed",
            "label": "Pilar 3: Inyección Embebida Directa Estímulo-EEG",
            "group": "novelty",
            "color": "#10b981",
            "size": 5.2,
            "category": "Novedad Central",
            "badge": "NOVEDAD CLAVE 3",
            "desc": "Estampado de códigos de evento del serious game directamente en los 3 bytes de cabecera de la trama SPI en tiempo real.",
            "rhetorical_question": "¿Cómo se garantiza que cada muestra de EEG sepa con absoluta certeza qué estímulo vio el niño?",
            "paragraph_text": "The microcontroller embeds stimulus flags directly into the 3-byte protocol header of each transmission packet via an external GPIO interrupt linked to the serious game engine, stamping event codes at the physical instant of analog-to-digital conversion.",
            "metrics": "104 bytes por paquete UDP a 250 Hz con cabecera atómica.",
            "novelty_claim": "Garantiza alineación exacta de fase para promediado de potenciales evocados ERP sin posprocesamiento.",
            "thesis_ref": "Capítulo 3 (Sección 3.4: Protocolo de Comunicación y Tramas), pág. 56",
            "pdf_page": 5,
            "section_ref": "Sección 3 (Materiales y Métodos)",
            "paper_blocks": ["abstract.slot-4", "materials-and-methods.mm-proposal"]
        },

        # =====================================================================
        # 5. DATASETS PROBADOS (PURPLE / VIOLET)
        # =====================================================================
        {
            "id": "dataset-hub",
            "label": "5. Datasets y Bancos Probados",
            "group": "dataset",
            "color": "#a855f7",
            "size": 7.0,
            "category": "Datasets Probados",
            "badge": "DIMENSIÓN 5 / EVIDENCIA EMPÍRICA",
            "desc": "Conjunto de datos empíricos de banco y registros fisiológicos humanos que validan la hipótesis del manuscrito.",
            "rhetorical_question": "¿Qué pruebas experimentales y conjuntos de datos sustentan las afirmaciones del artículo?",
            "paragraph_text": "Validation was conducted through a three-stage experimental protocol: precision bench testing with simulated microvolt signals, continuous streaming stress tests, and physiological ground-truth recording in human subjects.",
            "metrics": "3 protocolos metodológicos, 14.4 millones de muestras, registros in-vivo.",
            "novelty_claim": "Aporta datos de ground-truth instrumental y fisiológico replicables.",
            "thesis_ref": "Capítulo 4 (Resultados y Validación Experimental)",
            "pdf_page": 5,
            "section_ref": "Sección 4 (Setup Experimental)",
            "paper_blocks": ["experimental-setup.es-dataset", "experimental-setup.es-assessment"]
        },
        {
            "id": "ds-bench",
            "label": "1. Banco de Calibración 32-Ch (5–500 µV)",
            "group": "dataset",
            "color": "#a855f7",
            "size": 4.8,
            "category": "Datasets Probados",
            "badge": "BANCO INSTRUMENTAL",
            "desc": "Generador senoidal de microvoltios con divisor resistivo 1000:1 blindado para caracterizar la matriz analógica.",
            "rhetorical_question": "¿Cómo se comprobó la linealidad y distorsión armónica en microvoltios antes de las pruebas biológicas?",
            "paragraph_text": "A precision signal generator coupled with a shielded 1000:1 resistive divider fed calibrated sine waves (5--500 µV, 1--70 Hz) across all 32 channels to verify gain accuracy, inter-channel phase uniformity, and THD.",
            "metrics": "5–500 µV, 1–70 Hz, THD < -80 dB, atenuación precisa.",
            "novelty_claim": "Garantiza linealidad y calibración metrológica antes de la toma de señales biológicas.",
            "thesis_ref": "Capítulo 4 (Sección 4.1: Montaje de Calibración y Banco), Fig. 4.1",
            "pdf_page": 5,
            "section_ref": "Sección 4 (Setup Experimental)",
            "paper_blocks": ["experimental-setup.es-dataset", "results-and-discussion.rd-general-task"]
        },
        {
            "id": "ds-p300",
            "label": "2. Dataset Empírico P300 Oddball / Berger",
            "group": "dataset",
            "color": "#a855f7",
            "size": 5.0,
            "category": "Datasets Probados",
            "badge": "DATASET FISIOLÓGICO",
            "desc": "Registros electrofisiológicos in-vivo en reposo (efecto Berger ojos abiertos/cerrados) y paradigma Oddball atencional.",
            "rhetorical_question": "¿Qué evidencia fisiológica directa comprueba que las señales corresponden a dinámica cortical real?",
            "paragraph_text": "Recording at the occipital electrode O2 during an eyes-open vs. eyes-closed resting state protocol demonstrated clear Berger alpha rhythm attenuation. During eyes-closed intervals, spectral power in the 8--13 Hz band increased by 3.8 dB, providing indisputable proof of physiological ground-truth.",
            "metrics": "Incremento de 3.8 dB en banda alfa (8–13 Hz) en electrodo O2.",
            "novelty_claim": "Prueba concluyente de captura biológica cerebral con alta relación señal a ruido.",
            "thesis_ref": "Capítulo 4 (Sección 4.4: Validación In-Vivo Efecto Berger), Fig. 4.12",
            "pdf_page": 7,
            "section_ref": "Sección 5 (Resultados)",
            "paper_blocks": ["abstract.slot-5", "results-and-discussion.rd-cost"]
        },
        {
            "id": "ds-stress",
            "label": "3. Ensayo de Estrés Continuo (400 Minutos)",
            "group": "dataset",
            "color": "#a855f7",
            "size": 5.0,
            "category": "Datasets Probados",
            "badge": "BANCO DE RESISTENCIA",
            "desc": "Streaming ininterrumpido durante 6.6 horas a 250 Hz por canal generando 14.4 millones de muestras continuas.",
            "rhetorical_question": "¿Cómo se comprobó la confiabilidad y tolerancia a fallos del enlace de transmisión en sesiones largas?",
            "paragraph_text": "In long-term streaming endurance tests, the system operated continuously for 400 minutes, transmitting 1.44 x 10^7 samples with zero dropped packets and bounded inter-sample jitter (< 25 µs), demonstrating absolute link stability.",
            "metrics": "14,400,000 muestras, 0 paquetes descartados (0.0%), jitter entre muestras < 25 µs.",
            "novelty_claim": "Verifica estabilidad para sesiones terapéuticas prolongadas sin reinicio ni pérdida de contexto.",
            "thesis_ref": "Capítulo 4 (Sección 4.2: Evaluación de Pérdida de Paquetes), Fig. 4.6",
            "pdf_page": 6,
            "section_ref": "Sección 5 (Resultados)",
            "paper_blocks": ["abstract.slot-5", "results-and-discussion.rd-contribution-blocks"]
        },

        # =====================================================================
        # 6. MEDIDAS DE DESEMPEÑO Y MÉTODOS A COMPARAR (AMBER / YELLOW)
        # =====================================================================
        {
            "id": "eval-hub",
            "label": "6. Medidas de Desempeño y Comparación",
            "group": "eval",
            "color": "#eab308",
            "size": 7.0,
            "category": "Desempeño y Comparación",
            "badge": "DIMENSIÓN 6 / METROLOGÍA",
            "desc": "Métricas cuantitativas clave y comparación formal con OpenBCI Cyton, BEATS y sistemas clínicos.",
            "rhetorical_question": "¿Cuáles son los indicadores métricos rigurosos bajo los cuales MONEEG supera a las alternativas?",
            "paragraph_text": "Evaluation metrics included: (i) Input-Referred Noise Floor (Vpp and Vrms across 0.16--70 Hz); (ii) Transmission Stability (Packet Drop Rate over 400 minutes); (iii) Event Synchronization Jitter (logic analyzer measurement); and (iv) Physiological SNR Preservation.",
            "metrics": "µs de jitter, µVpp de ruido, dB de CMRR, % de pérdida.",
            "novelty_claim": "Define el estándar metrológico para auditar instrumentación BCI abierta.",
            "thesis_ref": "Capítulo 4 (Sección 4.3: Métricas de Comparación)",
            "pdf_page": 5,
            "section_ref": "Sección 4 (Setup Experimental)",
            "paper_blocks": ["experimental-setup.es-assessment", "results-and-discussion.rd-general-task"]
        },
        {
            "id": "metric-jitter",
            "label": "Métrica: Jitter Temporal (2.4 µs vs 18.5 ms)",
            "group": "eval",
            "color": "#eab308",
            "size": 5.2,
            "category": "Desempeño y Comparación",
            "badge": "MÉTRICA COMPARATIVA",
            "desc": "Medición con analizador lógico digital entre el flanco TTL de disparo del juego y el enganche en trama SPI.",
            "rhetorical_question": "¿Cuál es la superioridad cuantitativa del enganche por hardware frente al streaming por software?",
            "paragraph_text": "In hardware synchronization tests, the measured delay between external TTL trigger and header latching was 2.4 µs with σ = 0.35 µs, completely outperforming software LSL streaming pipelines (18.5 ± 6.2 ms) by over three orders of magnitude.",
            "metrics": "2.4 µs (MONEEG) vs 18.5 ms (LSL) vs 12.0 ms (OpenBCI) — más de 7,000x más veloz.",
            "novelty_claim": "Habilita la sincronización perfecta de componentes ERP rápidos (N200/P300).",
            "thesis_ref": "Capítulo 4 (Sección 4.3: Medición de Latencia y Jitter Temporal), Fig. 4.9",
            "pdf_page": 6,
            "section_ref": "Sección 5 (Resultados)",
            "paper_blocks": ["abstract.slot-6", "results-and-discussion.rd-contribution-blocks"]
        },
        {
            "id": "metric-noise",
            "label": "Métrica: Piso de Ruido (<1.1 µVpp vs >5 µVpp)",
            "group": "eval",
            "color": "#eab308",
            "size": 5.2,
            "category": "Desempeño y Comparación",
            "badge": "MÉTRICA ANALÓGICA",
            "desc": "Caracterización de banco con entradas a masa (50 Ω): media Vpp = 0.94 µV, σ = 0.14 µV, Vrms ≈ 0.16 µV.",
            "rhetorical_question": "¿Cómo se compara el piso de ruido de MONEEG frente a cascos de consumo y amplificadores clínicos?",
            "paragraph_text": "Across all 32 channels, the input-referred noise floor remained strictly under 1.1 µVpp (mean Vpp = 0.94 µV, σ = 0.14 µV, Vrms ≈ 0.16 µV). This matches gold-standard research amplifiers (BioSemi: ~0.8 µVpp) and significantly improves upon OpenBCI (~1.5 µVpp) and consumer devices (>5 µVpp).",
            "metrics": "Vpp = 0.94 µV en MONEEG vs 1.5 µV en OpenBCI vs >5.0 µV en cascos de consumo.",
            "novelty_claim": "Demuestra fidelidad de grado clínico a una fracción del costo comercial.",
            "thesis_ref": "Capítulo 4 (Sección 4.1: Caracterización de Ruido de Entrada), Fig. 4.3",
            "pdf_page": 6,
            "section_ref": "Sección 5 (Resultados)",
            "paper_blocks": ["abstract.slot-5", "results-and-discussion.rd-general-task"]
        },
        {
            "id": "metric-reliability",
            "label": "Métrica: Pérdida de Paquetes (0.0% en 1.44×10⁷ muestras)",
            "group": "eval",
            "color": "#eab308",
            "size": 4.8,
            "category": "Desempeño y Comparación",
            "badge": "MÉTRICA DE ENLACE",
            "desc": "Tasa de paquetes descartados y consistencia de intervalo de muestreo en streaming continuado.",
            "rhetorical_question": "¿Qué métrica demuestra la inmunidad frente a cuellos de botella y desbordes de memoria?",
            "paragraph_text": "Zero dropped packets across 1.44 x 10^7 samples proves that the DMA-driven bare-metal firmware completely resolves the preemption bottlenecks observed in single-MCU architectures like BEATS.",
            "metrics": "Tasa de descarte = 0.000%, jitter inter-muestra < 25 µs.",
            "novelty_claim": "Supera la confiabilidad de sistemas inalámbricos mononúcleo bajo carga sostenida.",
            "thesis_ref": "Capítulo 4 (Sección 4.2: Evaluación de Pérdida de Paquetes)",
            "pdf_page": 6,
            "section_ref": "Sección 5 (Resultados)",
            "paper_blocks": ["results-and-discussion.rd-contribution-blocks"]
        },

        # =====================================================================
        # 7. LAS 3 CONCLUSIONES MÁS FUERTES DE LOS RESULTADOS (CYAN / TEAL)
        # =====================================================================
        {
            "id": "conclusion-hub",
            "label": "7. 3 Conclusiones Más Fuertes",
            "group": "conclusion",
            "color": "#06b6d4",
            "size": 7.0,
            "category": "Conclusiones",
            "badge": "DIMENSIÓN 7 / IMPACTO",
            "desc": "Los tres hallazgos concluyentes respaldados por la evidencia numérica que cierran el manuscrito.",
            "rhetorical_question": "¿Cuáles son las 3 conclusiones científicas y traslacionales indiscutibles que deja el estudio?",
            "paragraph_text": "This paper demonstrated three conclusive findings: (1) sub-5 µs hardware synchronization fully protects ERP amplitude from jitter attenuation; (2) open-access modular design can achieve submicrovolt clinical noise floors; and (3) bare-metal DMA firmware guarantees zero-loss streaming endurance.",
            "metrics": "3 aportes comprobados H1, H2 y H3.",
            "novelty_claim": "Cierra el artículo con rigor científico y respuesta categórica a las hipótesis iniciales.",
            "thesis_ref": "Capítulo 5 (Conclusiones Generales de la Tesis)",
            "pdf_page": 8,
            "section_ref": "Sección 7 (Conclusiones)",
            "paper_blocks": ["conclusions.concl-block-1", "conclusions.concl-block-2", "conclusions.concl-block-3"]
        },
        {
            "id": "concl-sync-p300",
            "label": "Conclusión 1: Sincronía <5 µs Erradica Atenuación >40% P300",
            "group": "conclusion",
            "color": "#06b6d4",
            "size": 5.2,
            "category": "Conclusiones",
            "badge": "CONCLUSIÓN 1",
            "desc": "La inyección determinista de eventos en hardware restaura completamente la morfología y fase de potenciales evocados rápidos.",
            "rhetorical_question": "¿Cómo cambia el promediado de potenciales evocados al reemplazar software por interrupciones de hardware?",
            "paragraph_text": "First, deterministic sub-5 µs hardware stimulus injection eliminates the stochastic 10--50 ms timing jitter of software streaming protocols, preventing the >40% P300 amplitude attenuation that compromises single-trial ERP analysis in pediatric patients.",
            "metrics": "Preservación del 100% de la amplitud pico del P300 sin desenfoque temporal.",
            "novelty_claim": "Comprueba empíricamente la Hipótesis H1 del paper.",
            "thesis_ref": "Capítulo 5 (Conclusión 1 de la Tesis)",
            "pdf_page": 8,
            "section_ref": "Sección 7 (Conclusiones)",
            "paper_blocks": ["conclusions.concl-block-1", "abstract.slot-6"]
        },
        {
            "id": "concl-clinical-open",
            "label": "Conclusión 2: Calidad Clínica (<1.1 µVpp) en Hardware Abierto",
            "group": "conclusion",
            "color": "#06b6d4",
            "size": 5.2,
            "category": "Conclusiones",
            "badge": "CONCLUSIÓN 2",
            "desc": "La arquitectura modular 4x ADS1299 en cascada iguala la pureza de señal de amplificadores médicos comerciales.",
            "rhetorical_question": "¿Es posible alcanzar especificaciones de grado clínico con componentes de acceso abierto?",
            "paragraph_text": "Second, the cascaded 4x ADS1299 architecture with galvanic power isolation delivers an input-referred noise floor below 1.1 µVpp across all 32 channels, confirming that open-access hardware can match the signal fidelity of commercial laboratory amplifiers.",
            "metrics": "Ruido <1.1 µVpp, costo 85% menor que sistemas clínicos cerrados.",
            "novelty_claim": "Comprueba empíricamente la Hipótesis H2 del paper.",
            "thesis_ref": "Capítulo 5 (Conclusión 2 de la Tesis)",
            "pdf_page": 8,
            "section_ref": "Sección 7 (Conclusiones)",
            "paper_blocks": ["conclusions.concl-block-2", "abstract.slot-5"]
        },
        {
            "id": "concl-endurance",
            "label": "Conclusión 3: Transmisión Cero Pérdidas en Sesiones Largas",
            "group": "conclusion",
            "color": "#06b6d4",
            "size": 5.0,
            "category": "Conclusiones",
            "badge": "CONCLUSIÓN 3",
            "desc": "400 minutos continuos con 14.4 millones de muestras sin pérdida confirman estabilidad para terapias clínicas completas.",
            "rhetorical_question": "¿Qué garantiza que el sistema no colapse durante una intervención de neuroterapia prolongada?",
            "paragraph_text": "Third, the bare-metal DMA-driven firmware demonstrated zero dropped packets over 400 continuous streaming minutes, confirming the operational reliability required for demanding clinical and neurorehabilitation sessions.",
            "metrics": "14.4M muestras, 0 pérdidas, jitter inter-muestra acotado.",
            "novelty_claim": "Comprueba empíricamente la Hipótesis H3 del paper.",
            "thesis_ref": "Capítulo 5 (Conclusión 3 de la Tesis)",
            "pdf_page": 8,
            "section_ref": "Sección 7 (Conclusiones)",
            "paper_blocks": ["conclusions.concl-block-3", "results-and-discussion.rd-contribution-blocks"]
        },

        # =====================================================================
        # 8. LAS 2-3 LÍNEAS DE TRABAJO FUTURO MÁS RELEVANTES (PINK / FUCHSIA)
        # =====================================================================
        {
            "id": "future-hub",
            "label": "8. 2–3 Líneas de Trabajo Futuro",
            "group": "future",
            "color": "#ec4899",
            "size": 7.0,
            "category": "Trabajo Futuro",
            "badge": "DIMENSIÓN 8 / HORIZONTE",
            "desc": "Las líneas de desarrollo tecnológico y traslación clínica que marcan la continuidad del proyecto.",
            "rhetorical_question": "¿Cuáles son las siguientes etapas estratégicas para escalar el impacto de MONEEG?",
            "paragraph_text": "Future work will advance in three concrete directions: on-chip edge spatial filtering, extensive clinical validation across a larger pediatric ADHD cohort, and an ultra-low-power deterministic wireless link.",
            "metrics": "3 rutas de evolución: firmware on-chip, cohorte clínica y reducción de consumo.",
            "novelty_claim": "Demuestra visión a largo plazo y madurez traslacional ante revisores.",
            "thesis_ref": "Capítulo 5 (Trabajo Futuro y Recomendaciones)",
            "pdf_page": 8,
            "section_ref": "Sección 6 (Limitaciones) y Sección 7 (Conclusiones)",
            "paper_blocks": ["limitations.lim-closing", "conclusions.concl-block-4"]
        },
        {
            "id": "fut-edge-ica",
            "label": "Futuro 1: Filtrado Espacial en el Borde (ICA/CSP en MCU)",
            "group": "future",
            "color": "#ec4899",
            "size": 4.8,
            "category": "Trabajo Futuro",
            "badge": "FUTURO FIRMWARE",
            "desc": "Implementación de algoritmos de descomposición espacial y rechazo de artefactos directamente en procesadores ARM con FPU.",
            "rhetorical_question": "¿Cómo se puede limpiar la señal EEG de parpadeos en tiempo real sin sobrecargar el PC receptor?",
            "paragraph_text": "Incorporating real-time spatial filtering algorithms (such as embedded FastICA or Common Spatial Patterns) directly onto the Cortex-M4F microcontroller will enable on-chip ocular and muscular artifact rejection prior to wireless dispatch.",
            "metrics": "Reducción de latencia de preprocesamiento a sub-milisegundo.",
            "novelty_claim": "Avanza hacia un nodo BCI autónomo con cómputo en el borde (Edge AI).",
            "thesis_ref": "Capítulo 5 (Sección 5.2: Procesamiento Embebido en Tiempo Real)",
            "pdf_page": 8,
            "section_ref": "Sección 6 (Limitaciones)",
            "paper_blocks": ["limitations.lim-proposal-items", "conclusions.concl-block-4"]
        },
        {
            "id": "fut-clinical-cohort",
            "label": "Futuro 2: Ensayo Clínico Multicéntrico en Cohorte TDAH",
            "group": "future",
            "color": "#ec4899",
            "size": 5.0,
            "category": "Trabajo Futuro",
            "badge": "FUTURO TRASLACIONAL",
            "desc": "Validación extendida con 30+ niños diagnosticados con TDAH durante sesiones terapéuticas semanales con el juego Eagle Eye.",
            "rhetorical_question": "¿Qué se requiere para consolidar la evidencia de eficacia terapéutica en neurorrehabilitación pediátrica?",
            "paragraph_text": "A comprehensive multi-session clinical trial with a cohort of 30+ pediatric patients diagnosed with ADHD is planned to longitudinally quantify behavioral improvements and neuroplastic changes induced by Eagle Eye serious game training.",
            "metrics": "Cohorte n = 30+, protocolo de 12 semanas, métricas conductuales Conners-3.",
            "novelty_claim": "Aporta validación clínica longitudinal de grado médico bajo Minciencias-92056.",
            "thesis_ref": "Capítulo 5 (Sección 5.2: Recomendaciones de Ensayos Clínicos)",
            "pdf_page": 8,
            "section_ref": "Sección 6 (Limitaciones)",
            "paper_blocks": ["limitations.lim-validation-items", "conclusions.concl-block-4"]
        },
        {
            "id": "fut-wireless-deterministic",
            "label": "Futuro 3: Enlace Inalámbrico Ultra-Baja Potencia (<80 mA)",
            "group": "future",
            "color": "#ec4899",
            "size": 4.8,
            "category": "Trabajo Futuro",
            "badge": "FUTURO HARDWARE",
            "desc": "Transición a transceptores de capa física determinista (BLE 5.3 / ESP-NOW con TDMA) reduciendo el consumo de 220 mA a <80 mA.",
            "rhetorical_question": "¿Cómo se optimiza la autonomía energética para permitir jornadas completas de monitoreo ambulatorio?",
            "paragraph_text": "To extend battery autonomy beyond 4.5 hours, future revisions will implement custom TDMA time-slotted physical links (e.g., optimized BLE 5.3 PHY or proprietary 2.4 GHz protocols), targeting power consumption under 80 mA.",
            "metrics": "De 220 mA a <80 mA, autonomía extendida de 4.5h a >12h con batería de 1200 mAh.",
            "novelty_claim": "Elimina el consumo elevado de Wi-Fi manteniendo sincronismo determinista.",
            "thesis_ref": "Capítulo 5 (Sección 5.2: Optimización Energética de la Plataforma)",
            "pdf_page": 8,
            "section_ref": "Sección 6 (Limitaciones)",
            "paper_blocks": ["limitations.lim-failure-mode", "conclusions.concl-block-4"]
        }
    ],
    "links": [
        # Conexiones desde el Núcleo Central a los 8 Hubs
        {"source": "core-moneeg", "target": "app-hub", "label": "diseñado para", "value": 3.0},
        {"source": "core-moneeg", "target": "problem-hub", "label": "resuelve", "value": 3.5},
        {"source": "core-moneeg", "target": "sota-hub", "label": "supera", "value": 3.0},
        {"source": "core-moneeg", "target": "novelty-hub", "label": "sustentado en", "value": 4.0},
        {"source": "core-moneeg", "target": "dataset-hub", "label": "validado en", "value": 3.5},
        {"source": "core-moneeg", "target": "eval-hub", "label": "evaluado con", "value": 3.5},
        {"source": "core-moneeg", "target": "conclusion-hub", "label": "demuestra", "value": 4.0},
        {"source": "core-moneeg", "target": "future-hub", "label": "proyecta", "value": 3.0},

        # 1. Hub Aplicaciones -> Nodos Hijos
        {"source": "app-hub", "target": "app-adhd", "label": "prioriza", "value": 2.5},
        {"source": "app-hub", "target": "app-neurofeedback", "label": "habilita", "value": 2.5},
        {"source": "app-hub", "target": "app-serious-games", "label": "integra", "value": 2.5},

        # 2. Hub Problema -> Nodos Hijos
        {"source": "problem-hub", "target": "prob-jitter", "label": "identifica", "value": 2.5},
        {"source": "problem-hub", "target": "prob-noise", "label": "identifica", "value": 2.5},
        {"source": "problem-hub", "target": "prob-ergonomics", "label": "identifica", "value": 2.5},

        # 3. Hub SOTA -> Nodos Hijos
        {"source": "sota-hub", "target": "sota-beats", "label": "compara frente a", "value": 2.0},
        {"source": "sota-hub", "target": "sota-lsl", "label": "compara frente a", "value": 2.0},
        {"source": "sota-hub", "target": "sota-openbci", "label": "compara frente a", "value": 2.0},
        {"source": "sota-hub", "target": "sota-consumer", "label": "compara frente a", "value": 2.0},
        {"source": "sota-hub", "target": "sota-vr-oddball", "label": "compara frente a", "value": 2.0},

        # 4. Hub Novedad -> Nodos Hijos
        {"source": "novelty-hub", "target": "nov-sync", "label": "despliega", "value": 3.0},
        {"source": "novelty-hub", "target": "nov-afe", "label": "despliega", "value": 3.0},
        {"source": "novelty-hub", "target": "nov-trigger-embed", "label": "despliega", "value": 3.0},

        # 5. Hub Datasets -> Nodos Hijos
        {"source": "dataset-hub", "target": "ds-bench", "label": "incluye", "value": 2.5},
        {"source": "dataset-hub", "target": "ds-p300", "label": "incluye", "value": 2.5},
        {"source": "dataset-hub", "target": "ds-stress", "label": "incluye", "value": 2.5},

        # 6. Hub Métricas -> Nodos Hijos
        {"source": "eval-hub", "target": "metric-jitter", "label": "mide", "value": 2.5},
        {"source": "eval-hub", "target": "metric-noise", "label": "mide", "value": 2.5},
        {"source": "eval-hub", "target": "metric-reliability", "label": "mide", "value": 2.5},

        # 7. Hub Conclusiones -> Nodos Hijos
        {"source": "conclusion-hub", "target": "concl-sync-p300", "label": "afirma", "value": 3.0},
        {"source": "conclusion-hub", "target": "concl-clinical-open", "label": "afirma", "value": 3.0},
        {"source": "conclusion-hub", "target": "concl-endurance", "label": "afirma", "value": 3.0},

        # 8. Hub Futuro -> Nodos Hijos
        {"source": "future-hub", "target": "fut-edge-ica", "label": "propone", "value": 2.5},
        {"source": "future-hub", "target": "fut-clinical-cohort", "label": "propone", "value": 2.5},
        {"source": "future-hub", "target": "fut-wireless-deterministic", "label": "propone", "value": 2.5},

        # Enlaces Semánticos Transversales (Cruces Críticos de Novedad)
        {"source": "prob-jitter", "target": "sota-lsl", "label": "presente en", "value": 2.0},
        {"source": "nov-sync", "target": "prob-jitter", "label": "elimina", "value": 3.0},
        {"source": "nov-sync", "target": "sota-lsl", "label": "supera 18.5 ms de", "value": 2.5},
        {"source": "metric-jitter", "target": "nov-sync", "label": "corrobora 2.4 µs en", "value": 3.0},
        {"source": "concl-sync-p300", "target": "nov-sync", "label": "respaldada por", "value": 3.0},
        {"source": "concl-sync-p300", "target": "app-adhd", "label": "habilita diagnóstico en", "value": 2.5},

        {"source": "nov-afe", "target": "prob-noise", "label": "reduce a <1.1 µVpp", "value": 3.0},
        {"source": "nov-afe", "target": "sota-openbci", "label": "duplica canales frente a", "value": 2.0},
        {"source": "metric-noise", "target": "nov-afe", "label": "verifica 0.94 µVpp en", "value": 3.0},
        {"source": "concl-clinical-open", "target": "nov-afe", "label": "confirma fidelidad de", "value": 3.0},

        {"source": "nov-trigger-embed", "target": "app-serious-games", "label": "acopla directamente a", "value": 3.0},
        {"source": "ds-p300", "target": "app-serious-games", "label": "registrado durante", "value": 2.5},
        {"source": "ds-bench", "target": "nov-afe", "label": "calibra matriz de", "value": 2.5},
        {"source": "ds-stress", "target": "metric-reliability", "label": "suministra datos a", "value": 3.0},
        {"source": "concl-endurance", "target": "ds-stress", "label": "sustentada en", "value": 3.0},

        {"source": "fut-edge-ica", "target": "nov-sync", "label": "evoluciona firmware de", "value": 2.0},
        {"source": "fut-clinical-cohort", "target": "app-adhd", "label": "extiende ensayo en", "value": 2.5},
        {"source": "fut-wireless-deterministic", "target": "nov-trigger-embed", "label": "optimiza enlace de", "value": 2.0}
    ]
}


def build_novelty_graph() -> dict[str, Any]:
    """Return the complete semantic novelty graph for MONEEG."""
    return NOVELTY_GRAPH_DATA


def build_novelty_viewer_html() -> str:
    """Generate the full responsive 3D WebGL viewer for the novelty graph,
    matching the exact style, typography, libraries, and constellation aesthetics of SOTA Atlas."""
    graph_json = json.dumps(NOVELTY_GRAPH_DATA, ensure_ascii=False)
    
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Grafo 3D de Novedad e Ideas del Manuscrito — MONEEG</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <script src="https://unpkg.com/3d-force-graph@1.73.3/dist/3d-force-graph.min.js"></script>
  <style>
    html, body {{
      height: 100%;
      margin: 0;
      padding: 10px 14px;
      box-sizing: border-box;
      background: #0a0a10;
      color: #e4e4ed;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    h1 {{
      font-size: 16px;
      font-weight: 600;
      margin: 0 0 4px;
      letter-spacing: .02em;
      color: #f1f5f9;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    h1 small {{
      font-size: 11px;
      font-weight: 400;
      color: #64748b;
      letter-spacing: 0;
    }}
    #panel {{
      color: #9aa3bd;
      font-size: 12px;
      margin: 0 0 6px;
      line-height: 1.35;
    }}
    #famlegend, #rellegend, #toolbar {{
      margin: 0 0 5px;
      font-size: 12px;
      color: #9aa3bd;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
    }}
    #famlegend em, #rellegend em {{
      font-style: normal;
      font-weight: 600;
      margin-right: 6px;
      color: #cbd5e1;
    }}
    .famchip {{
      margin: 2px 4px 2px 0;
      padding: 2.5px 10px;
      cursor: pointer;
      border-radius: 12px;
      border: 1px solid #334155;
      background: #14172a;
      color: #e4e4ed;
      font-size: 11.5px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s ease;
      user-select: none;
    }}
    .famchip:hover {{
      background: #1e243d;
      border-color: #475569;
    }}
    .famchip.on {{
      font-weight: 700;
      box-shadow: 0 0 10px currentColor;
    }}
    .famchip-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      display: inline-block;
    }}
    .dot {{
      display: inline-block;
      width: 14px;
      height: 0;
      border-top: 2px solid;
      margin: 0 3px 2px 8px;
      vertical-align: middle;
    }}
    #toolbar {{
      gap: 6px;
    }}
    #toolbar button {{
      font-size: 12px;
      padding: 3.5px 11px;
      cursor: pointer;
      background: #14172a;
      color: #e4e4ed;
      border: 1px solid #2a3350;
      border-radius: 6px;
      transition: background 0.15s, border-color 0.15s;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    #toolbar button:hover {{
      background: #1e243d;
      border-color: #38bdf8;
    }}
    #toolbar button.active {{
      background: #0284c7;
      border-color: #38bdf8;
      color: #fff;
    }}
    #nodeSearchInput {{
      background: #14172a;
      border: 1px solid #2a3350;
      border-radius: 6px;
      padding: 3px 10px;
      font-size: 12px;
      color: #e4e4ed;
      outline: none;
      margin-left: 6px;
      width: 220px;
    }}
    #nodeSearchInput:focus {{
      border-color: #38bdf8;
      box-shadow: 0 0 8px rgba(56, 189, 248, 0.3);
    }}
    .sky {{
      flex: 1 1 auto;
      min-height: 420px;
      width: 100%;
      background: #0a0a10;
      border: 1px solid #1e2236;
      border-radius: 10px;
      overflow: hidden;
      position: relative;
      cursor: grab;
    }}
    .sky:active {{
      cursor: grabbing;
    }}
    #3d-graph {{
      width: 100%;
      height: 100%;
    }}

    /* Side Inspector Card (Modal Style matching SOTA Atlas) */
    .inspector-card {{
      position: absolute;
      top: 12px;
      right: 12px;
      width: 440px;
      max-width: calc(100vw - 28px);
      max-height: calc(100% - 24px);
      background: #11131f;
      border: 1px solid #2a3350;
      border-radius: 10px;
      padding: 16px 18px;
      overflow-y: auto;
      z-index: 20;
      box-shadow: 0 0 40px rgba(14, 165, 233, 0.2);
      display: none;
      scrollbar-width: thin;
    }}
    .inspector-card__header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid #1e243d;
    }}
    .inspector-badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .inspector-close {{
      background: #1a1d2e;
      border: 1px solid #2a3350;
      color: #e4e4ed;
      font-size: 13px;
      padding: 1px 8px;
      border-radius: 4px;
      cursor: pointer;
    }}
    .inspector-close:hover {{
      background: #2a3350;
    }}
    .inspector-title {{
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 6px;
      line-height: 1.3;
    }}
    .inspector-desc {{
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.5;
      margin-bottom: 12px;
    }}
    .quote {{
      font-style: italic;
      color: #b9c4de;
      border-left: 3px solid #10b981;
      margin: 10px 0;
      padding: 8px 12px;
      background: rgba(16, 185, 129, 0.05);
      border-radius: 0 6px 6px 0;
      font-family: Georgia, serif;
      line-height: 1.55;
      font-size: 12.5px;
    }}
    .inspector-meta-block {{
      margin-bottom: 10px;
      font-size: 12px;
      line-height: 1.45;
    }}
    .inspector-meta-block strong {{
      color: #cbd5e1;
      display: block;
      margin-bottom: 3px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .inspector-meta-block em {{
      color: #38bdf8;
      font-style: normal;
    }}
    .inspector-meta-block span {{
      color: #94a3b8;
    }}
    .inspector-blocks {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-top: 4px;
    }}
    .block-pill {{
      background: rgba(56, 189, 248, 0.12);
      border: 1px solid rgba(56, 189, 248, 0.25);
      color: #38bdf8;
      padding: 1px 6px;
      border-radius: 3px;
      font-size: 10.5px;
      font-family: monospace;
    }}
    .btn-action-jump {{
      width: 100%;
      background: #0284c7;
      color: #fff;
      border: 1px solid #38bdf8;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 10px;
      transition: background 0.15s, transform 0.15s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }}
    .btn-action-jump:hover {{
      background: #0369a1;
      transform: translateY(-1px);
    }}
  </style>
</head>
<body>

  <!-- Top Title and Instructions (Atlas Style) -->
  <h1>
    <span>🕸️ Grafo 3D de Novedad e Ideas del Manuscrito — MONEEG</span>
    <small>Elsevier Biomedical Signal Processing and Control · Minciencias-92056</small>
  </h1>
  <div id="panel">Arrastra con el ratón para rotar (órbita suave), rueda para zoom 3D sensible, clic derecho para desplazar. Clic en cualquier nodo para inspeccionar evidencia y párrafos. Usa los chips de colores para filtrar por las 8 dimensiones clave.</div>

  <!-- Legend & Color Grouping Chips (Atlas Style) -->
  <div id="famlegend"><em>8 Dimensiones Clave:</em> <span id="famchips"></span></div>
  <div id="rellegend"><em>Enlaces:</em> <span class="dot" style="border-color:#38bdf8"></span>arquitectura global <span class="dot" style="border-color:#10b981"></span>novedad vendida <span class="dot" style="border-color:#f43f5e"></span>resuelve brecha <span class="dot" style="border-color:#a855f7"></span>evidencia experimental <span class="dot" style="border-color:#eab308"></span>métricas comparativas</div>

  <!-- Toolbar Controls (Atlas Style) -->
  <div id="toolbar">
    <button id="zoomin" title="Acercar cámara">🔍 Zoom +</button>
    <button id="zoomout" title="Alejar cámara">🔍 Zoom −</button>
    <button id="zoomreset" title="Restablecer vista centrada">↺ Reset</button>
    <button id="btnAutoRotate" class="active" title="Pausar o reanudar giro suave de la cámara">⏸️ Pausar giro</button>
    <button id="btnWheelMode" title="Alternar función de la rueda del ratón">🖱️ Rueda: Zoom 3D</button>
    <input type="text" id="nodeSearchInput" placeholder="🔍 Buscar nodo, métrica o párrafo..." oninput="searchNodes(this.value)">
  </div>

  <!-- Sky Canvas Container -->
  <div id="sky" class="sky">
    <div id="3d-graph"></div>

    <!-- Side Inspector Drawer / Modal -->
    <aside class="inspector-card" id="inspectorCard">
      <div class="inspector-card__header">
        <span class="inspector-badge" id="inspBadge">Categoría</span>
        <button class="inspector-close" onclick="closeInspector()">✕ cerrar</button>
      </div>
      <div class="inspector-title" id="inspTitle">Nombre del Nodo</div>
      <p class="inspector-desc" id="inspDesc">Descripción detallada del nodo y su rol en la investigación.</p>
      
      <!-- Extracto del Párrafo del Manuscrito -->
      <div id="inspParagraphBox" style="display: none; margin-bottom: 10px;">
        <strong style="font-size: 11px; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.04em;">📜 Extracto del Párrafo del Manuscrito (LaTeX)</strong>
        <div class="quote" id="inspParagraphText">—</div>
      </div>

      <!-- Pregunta Retórica que Responde -->
      <div class="inspector-meta-block" id="inspQuestionBox">
        <strong>❓ Pregunta Retórica que Responde</strong>
        <em id="inspQuestion">—</em>
      </div>

      <!-- Respuesta a la Novedad para Elsevier -->
      <div class="inspector-meta-block">
        <strong>🎯 Respuesta a la Novedad (Elsevier BSPC)</strong>
        <span id="inspNovelty">—</span>
      </div>

      <!-- Métrica Cuantitativa -->
      <div class="inspector-meta-block">
        <strong>⚡ Métrica / Hecho Cuantitativo</strong>
        <span id="inspMetrics">—</span>
      </div>

      <!-- Sustento en la Tesis de Julián -->
      <div class="inspector-meta-block">
        <strong>📖 Sustento en la Tesis de Maestría de Julián</strong>
        <span id="inspThesis">—</span>
      </div>

      <!-- Bloques Canónicos y Ubicación -->
      <div class="inspector-meta-block">
        <strong>📑 Bloques Canónicos y Ubicación</strong>
        <div style="font-size: 11px; color: #94a3b8; margin-bottom: 4px;" id="inspLocation">—</div>
        <div class="inspector-blocks" id="inspBlocks"></div>
      </div>

      <button class="btn-action-jump" id="btnJumpPdf" onclick="jumpToPaperPreview()">
        📄 Ir a esta Sección en el Visor PDF (<span id="inspPdfPage">Pág. 1</span>) ↗
      </button>
    </aside>
  </div>

  <script>
    const graphData = {graph_json};

    let isRotating = true;
    let selectedNode = null;
    let activeGroup = null;
    let hoverNode = null;
    let targetPdfPage = 1;
    let wheelMode = 'zoom'; // 'zoom' | 'page'

    const highlightNodes = new Set();
    const highlightLinks = new Set();

    const elem = document.getElementById('3d-graph');
    const Graph = ForceGraph3D()(elem)
      .graphData(graphData)
      .backgroundColor('#0a0a10')
      .showNavInfo(false)
      .nodeLabel(node => `${{node.label}} [${{node.category}}]`)
      .nodeVal(node => node.size || 5)
      .nodeResolution(24)
      .nodeColor(node => {{
        if (highlightNodes.size > 0 && !highlightNodes.has(node.id)) {{
          return 'rgba(45, 52, 75, 0.22)';
        }}
        return node.color || '#38bdf8';
      }})
      .linkWidth(link => {{
        if (highlightLinks.size > 0 && !highlightLinks.has(link)) return 0.5;
        return link.value ? link.value * 0.7 : 1.2;
      }})
      .linkColor(link => {{
        if (highlightLinks.size > 0 && !highlightLinks.has(link)) {{
          return 'rgba(25, 30, 48, 0.08)';
        }}
        if (link.source && (link.source.group === 'novelty' || link.source === 'novelty')) return 'rgba(16, 185, 129, 0.55)';
        if (link.source && (link.source.group === 'problem' || link.source === 'problem')) return 'rgba(244, 63, 94, 0.45)';
        return 'rgba(56, 189, 248, 0.35)';
      }})
      .linkDirectionalParticles(2)
      .linkDirectionalParticleWidth(link => {{
        if (highlightLinks.size > 0 && !highlightLinks.has(link)) return 0;
        return 1.6;
      }})
      .linkDirectionalParticleSpeed(0.005)
      .linkDirectionalParticleColor(link => {{
        if (link.source && (link.source.group === 'novelty' || link.source === 'novelty')) return '#10b981';
        if (link.source && (link.source.group === 'problem' || link.source === 'problem')) return '#f43f5e';
        return '#38bdf8';
      }})
      .linkLabel(link => link.label)
      .onNodeHover(node => {{
        elem.style.cursor = node ? 'pointer' : null;
        hoverNode = node;
        updateHighlight();
        Graph.nodeColor(Graph.nodeColor()).linkColor(Graph.linkColor()).linkWidth(Graph.linkWidth());
      }})
      .onNodeClick(node => {{
        selectNode(node);
      }})
      .onBackgroundClick(() => {{
        closeInspector();
      }});

    // Configure OrbitControls for maximum responsiveness, buttery smooth damping, and non-blocking auto-rotate
    setTimeout(() => {{
      const controls = Graph.controls();
      if (controls) {{
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
        controls.rotateSpeed = 0.85;
        controls.zoomSpeed = 1.35;
        controls.panSpeed = 0.85;
        controls.enableZoom = true;
        controls.autoRotate = isRotating;
        controls.autoRotateSpeed = 0.7;

        // Yield auto-rotation gently when user starts manipulating
        controls.addEventListener('start', () => {{
          if (isRotating) {{
            controls.autoRotate = false;
          }}
        }});
        controls.addEventListener('end', () => {{
          if (isRotating && !selectedNode) {{
            controls.autoRotate = true;
          }}
        }});
      }}
    }}, 200);

    function updateHighlight() {{
      highlightNodes.clear();
      highlightLinks.clear();

      if (hoverNode) {{
        highlightNodes.add(hoverNode.id);
        graphData.links.forEach(l => {{
          const sId = typeof l.source === 'object' ? l.source.id : l.source;
          const tId = typeof l.target === 'object' ? l.target.id : l.target;
          if (sId === hoverNode.id || tId === hoverNode.id) {{
            highlightLinks.add(l);
            highlightNodes.add(sId);
            highlightNodes.add(tId);
          }}
        }});
      }} else if (activeGroup) {{
        graphData.nodes.forEach(n => {{
          if (n.group === activeGroup || n.id === 'core-moneeg') {{
            highlightNodes.add(n.id);
          }}
        }});
        graphData.links.forEach(l => {{
          const sId = typeof l.source === 'object' ? l.source.id : l.source;
          const tId = typeof l.target === 'object' ? l.target.id : l.target;
          if (highlightNodes.has(sId) && highlightNodes.has(tId)) {{
            highlightLinks.add(l);
          }}
        }});
      }}
    }}

    function toggleRotate() {{
      isRotating = !isRotating;
      const controls = Graph.controls();
      if (controls) {{
        controls.autoRotate = isRotating;
      }}
      const btn = document.getElementById('btnAutoRotate');
      btn.innerHTML = isRotating ? '⏸️ Pausar giro' : '▶️ Reanudar giro';
      btn.classList.toggle('active', isRotating);
    }}
    document.getElementById('btnAutoRotate').addEventListener('click', toggleRotate);

    function toggleWheelMode() {{
      wheelMode = (wheelMode === 'zoom') ? 'page' : 'zoom';
      const btn = document.getElementById('btnWheelMode');
      btn.innerHTML = wheelMode === 'zoom' ? '🖱️ Rueda: Zoom 3D' : '📜 Rueda: Scroll Página';
      btn.classList.toggle('active', wheelMode === 'page');
    }}
    document.getElementById('btnWheelMode').addEventListener('click', toggleWheelMode);

    // Mouse wheel delegate: forward to parent page scroll when hovering UI, holding Shift, or in page scroll mode
    window.addEventListener('wheel', (e) => {{
      const isUI = e.target.closest('#famlegend, #rellegend, #toolbar, h1, #panel, .inspector-card');
      if (wheelMode === 'page' || e.shiftKey || isUI) {{
        if (window.parent && window.parent !== window) {{
          window.parent.postMessage({{ type: 'page_scroll', deltaY: e.deltaY }}, '*');
        }}
      }}
    }}, {{ passive: true }});

    document.getElementById('zoomin').addEventListener('click', () => {{
      const pos = Graph.cameraPosition();
      Graph.cameraPosition({{ x: pos.x * 0.72, y: pos.y * 0.72, z: pos.z * 0.72 }}, null, 350);
    }});

    document.getElementById('zoomout').addEventListener('click', () => {{
      const pos = Graph.cameraPosition();
      Graph.cameraPosition({{ x: pos.x * 1.35, y: pos.y * 1.35, z: pos.z * 1.35 }}, null, 350);
    }});

    document.getElementById('zoomreset').addEventListener('click', () => {{
      isRotating = true;
      const controls = Graph.controls();
      if (controls) controls.autoRotate = true;
      document.getElementById('btnAutoRotate').innerHTML = '⏸️ Pausar giro';
      document.getElementById('btnAutoRotate').classList.add('active');
      activeGroup = null;
      document.querySelectorAll('.famchip').forEach(c => {{
        c.classList.remove('on');
        c.style.background = '#14172a';
        c.style.color = '#e4e4ed';
      }});
      updateHighlight();
      Graph.nodeColor(Graph.nodeColor()).linkColor(Graph.linkColor()).linkWidth(Graph.linkWidth());
      Graph.cameraPosition({{ x: 0, y: 30, z: 420 }}, {{ x: 0, y: 0, z: 0 }}, 800);
    }});

    function selectNode(node) {{
      selectedNode = node;
      const controls = Graph.controls();
      if (controls) controls.autoRotate = false;

      const dist = 160;
      Graph.cameraPosition(
        {{ x: node.x + dist * 0.7, y: node.y + dist * 0.35, z: node.z + dist * 0.7 }},
        {{ x: node.x, y: node.y, z: node.z }},
        900
      );

      const card = document.getElementById('inspectorCard');
      card.style.display = 'block';
      
      const badge = document.getElementById('inspBadge');
      badge.textContent = node.badge || node.category;
      badge.style.background = `${{node.color}}25`;
      badge.style.color = node.color;
      badge.style.border = `1px solid ${{node.color}}`;

      document.getElementById('inspTitle').textContent = node.label;
      document.getElementById('inspDesc').textContent = node.desc;
      document.getElementById('inspMetrics').textContent = node.metrics || '—';
      document.getElementById('inspNovelty').textContent = node.novelty_claim || '—';
      document.getElementById('inspThesis').textContent = node.thesis_ref || 'Tesis de Maestría';

      const paraBox = document.getElementById('inspParagraphBox');
      const paraText = document.getElementById('inspParagraphText');
      if (node.paragraph_text) {{
        paraBox.style.display = 'block';
        paraText.textContent = `"${{node.paragraph_text}}"`;
      }} else {{
        paraBox.style.display = 'none';
      }}

      const qBox = document.getElementById('inspQuestionBox');
      const qText = document.getElementById('inspQuestion');
      if (node.rhetorical_question) {{
        qBox.style.display = 'block';
        qText.textContent = `"${{node.rhetorical_question}}"`;
      }} else {{
        qBox.style.display = 'none';
      }}

      targetPdfPage = node.pdf_page || 1;
      document.getElementById('inspPdfPage').textContent = `Pág. ${{targetPdfPage}}`;
      document.getElementById('inspLocation').textContent = `${{node.section_ref || 'Manuscrito'}} · Ubicación en documento: Página ${{targetPdfPage}}`;

      const blocksContainer = document.getElementById('inspBlocks');
      blocksContainer.innerHTML = '';
      (node.paper_blocks || []).forEach(b => {{
        const pill = document.createElement('span');
        pill.className = 'block-pill';
        pill.textContent = b;
        blocksContainer.appendChild(pill);
      }});
    }}

    function closeInspector() {{
      document.getElementById('inspectorCard').style.display = 'none';
      selectedNode = null;
      const controls = Graph.controls();
      if (controls && isRotating) {{
        controls.autoRotate = true;
      }}
    }}

    // Build Family Legend Chips (Exact 8 Pillars matching the User Specification)
    const GROUPS_META = [
      {{ id: 'core', label: 'MONEEG Global', color: '#38bdf8' }},
      {{ id: 'app', label: '1. Aplicaciones', color: '#0ea5e9' }},
      {{ id: 'problem', label: '2. Problema Central', color: '#f43f5e' }},
      {{ id: 'sota', label: '3. 5 Ideas SOTA', color: '#fb7185' }},
      {{ id: 'novelty', label: '4. Novedad (3 Pilares)', color: '#10b981' }},
      {{ id: 'dataset', label: '5. Datasets Probados', color: '#a855f7' }},
      {{ id: 'eval', label: '6. Métricas & Comparación', color: '#eab308' }},
      {{ id: 'conclusion', label: '7. 3 Conclusiones', color: '#06b6d4' }},
      {{ id: 'future', label: '8. Trabajo Futuro', color: '#ec4899' }}
    ];

    const chipsContainer = document.getElementById('famchips');
    GROUPS_META.forEach(g => {{
      const count = graphData.nodes.filter(n => n.group === g.id).length;
      if (count === 0) return;
      const chip = document.createElement('span');
      chip.className = 'famchip';
      chip.dataset.group = g.id;
      chip.style.borderColor = g.color;
      chip.innerHTML = `<span class="famchip-dot" style="background:${{g.color}}"></span>${{g.label}} (${{count}})`;
      
      chip.addEventListener('click', () => {{
        if (activeGroup === g.id) {{
          activeGroup = null;
          chip.classList.remove('on');
          chip.style.background = '#14172a';
          chip.style.color = '#e4e4ed';
        }} else {{
          activeGroup = g.id;
          document.querySelectorAll('.famchip').forEach(c => {{
            c.classList.remove('on');
            c.style.background = '#14172a';
            c.style.color = '#e4e4ed';
          }});
          chip.classList.add('on');
          chip.style.background = g.color;
          chip.style.color = '#0a0a10';
        }}
        updateHighlight();
        Graph.nodeColor(Graph.nodeColor()).linkColor(Graph.linkColor()).linkWidth(Graph.linkWidth());
      }});

      chipsContainer.appendChild(chip);
    }});

    function searchNodes(query) {{
      if (!query || !query.trim()) {{
        activeGroup = null;
        updateHighlight();
        Graph.nodeColor(Graph.nodeColor()).linkColor(Graph.linkColor()).linkWidth(Graph.linkWidth());
        return;
      }}
      const q = query.toLowerCase().trim();
      const match = graphData.nodes.find(n => 
        n.label.toLowerCase().includes(q) ||
        (n.desc && n.desc.toLowerCase().includes(q)) ||
        (n.paragraph_text && n.paragraph_text.toLowerCase().includes(q)) ||
        (n.metrics && n.metrics.toLowerCase().includes(q)) ||
        (n.novelty_claim && n.novelty_claim.toLowerCase().includes(q))
      );
      if (match) {{
        selectNode(match);
      }}
    }}

    function jumpToPaperPreview() {{
      if (window.parent && window.parent.jumpToPdfPage) {{
        window.parent.jumpToPdfPage(targetPdfPage);
      }} else if (window.parent && window.parent.navigateTab) {{
        window.parent.navigateTab('preview');
      }} else {{
        window.open('/#preview', '_blank');
      }}
    }}
  </script>
</body>
</html>"""

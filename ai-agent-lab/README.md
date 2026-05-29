# AI Agent Lab — 소스코드 기능 정리

## 디렉토리 구조

```
ai-agent-lab/
├── common/                          # 공통 유틸리티
│   ├── utils.py                     # 공통 함수 및 보안 유틸리티
│   └── openai_compat.py             # Groq/OpenAI 호환 래퍼
├── m02_tool_use/
│   └── lab_tools_chatgpt.py         # MODULE 2: 금융 Tool Calling
├── m03_memory_rag/
│   └── lab_rag_pipeline_chatgpt.py  # MODULE 3: 금융 규정 RAG Q&A
├── m04_single_agent/
│   └── lab_loan_review_chatgpt.py   # MODULE 4: 여신심사 자동화 에이전트
└── m05_monitoring/
    └── lab_security_monitoring_chatgpt.py  # MODULE 5: 보안 & 모니터링
```

---

## 기술 스택

| 항목 | 내용 |
|------|------|
| **LLM API** | Groq (OpenAI 호환) |
| **기본 모델** | `llama-3.3-70b-versatile` (정확도), `llama-3.1-8b-instant` (빠름) |
| **임베딩** | HuggingFace `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **벡터 DB** | FAISS (로컬) |
| **LangChain** | 텍스트 분할, RetrievalQA 체인, 메모리 관리 |
| **모니터링** | LangFuse (선택적, 미설치 시 로컬 로깅 대체) |
| **환경변수** | `GROQ_API_KEY` (`.env` 파일) |

---

## 실행 방법

```powershell
cd C:\Users\user\Desktop\kang-ai-agent\ai-agent-lab

# MODULE 2: Tool Calling 테스트
python m02_tool_use/lab_tools_chatgpt.py
python m02_tool_use/lab_tools_chatgpt.py --interactive

# MODULE 3: RAG Q&A
python m03_memory_rag/lab_rag_pipeline_chatgpt.py
python m03_memory_rag/lab_rag_pipeline_chatgpt.py --interactive

# MODULE 4: 여신심사 에이전트
python m04_single_agent/lab_loan_review_chatgpt.py

# MODULE 5: 보안 & 모니터링
python m05_monitoring/lab_security_monitoring_chatgpt.py
```

---

## 공통 모듈 (`common/`)

### `utils.py` — 공통 유틸리티

| 기능 | 함수/클래스 | 설명 |
|------|------------|------|
| **API 클라이언트** | `get_groq_client()` | Groq API 클라이언트 반환 (OpenAI SDK + base_url) |
| **모델 상수** | `MODELS` | `groq-large` / `groq-small` / `groq-fast` 모델명 정의 |
| **모델 라우팅** | `MODEL_ROUTING` | 작업 유형별 최적 모델 자동 선택 |
| | `get_model(task_type)` | 작업 유형에 따른 모델명 반환 |
| **PII 마스킹** | `mask_pii(text)` | 주민번호·전화번호·계좌번호·카드번호·이메일 자동 마스킹 |
| **인젝션 탐지** | `detect_prompt_injection(user_input)` | Prompt Injection 시도 탐지 (한국어/영어) |
| **재시도** | `@retry_on_api_error(max_attempts, base_delay)` | API 오류 시 지수 백오프 재시도 데코레이터 |
| **시간 유틸리티** | `now_kst_str()` | 현재 시각 ISO 포맷 반환 |
| | `elapsed_ms(start)` | 경과 시간(ms) 계산 |
| **출력 포맷터** | `Printer` | 컬러 터미널 출력 (`header`, `section`, `success`, `warn`, `error`, `kv`) |
| **로깅** | `get_logger(name)` | 모듈별 로거 반환 |

**모델 라우팅 기준:**

| 작업 유형 | 모델 |
|----------|------|
| `loan_review`, `large_loan`, `investment_report`, `customer_qa`, `report_draft` | `llama-3.3-70b-versatile` |
| `fds_check`, `simple_faq`, `classification` | `llama-3.1-8b-instant` |

---

### `openai_compat.py` — Groq/OpenAI 호환 래퍼

Groq API를 OpenAI Chat Completions 형식으로 통일하는 어댑터 레이어.

| 함수 | 설명 |
|------|------|
| `map_model_name(model_name)` | Claude 모델명 → Groq 모델명 변환 |
| `convert_anthropic_tools_to_openai(tools)` | Anthropic 도구 형식 → OpenAI 형식 변환 |
| `build_openai_messages(messages, system)` | 시스템 메시지 주입 포함 메시지 리스트 구성 |
| `create_chat_completion(...)` | Chat Completions API 호출 통합 래퍼 |
| `completion_text(completion)` | 응답에서 텍스트 추출 |
| `prompt_tokens(completion)` | 입력 토큰 수 반환 |
| `completion_tokens(completion)` | 출력 토큰 수 반환 |
| `finish_reason(completion)` | 완료 이유 반환 |
| `assistant_message_with_tool_calls(message)` | Tool Call 메시지 형식 변환 |

---

## MODULE 2: 금융 Tool Calling (`m02_tool_use/`)

**학습 목표:** OpenAI 호환 Function Calling 구조 이해 및 ReAct 루프 구현

### 금융 Tool 4종

| Tool | 설명 | 입력 | 출력 |
|------|------|------|------|
| `calculate_loan_payment` | 원리금균등상환 계산 | 원금, 연이율, 기간(개월) | 월상환액, 총상환액, 총이자, 이자비중 |
| `search_financial_news` | 금융 뉴스 검색 | 검색어, 건수(기본 3) | 뉴스 목록 (Mock 데이터) |
| `get_exchange_rate` | 환율 조회 | 통화쌍 (USD/KRW 등) | 환율, 전일대비, 등락률 (Mock) |
| `check_credit_score` | 신용점수 조회 | 고객 ID (C001~C004) | 신용점수, 등급, 연체여부 (Mock) |

### 주요 함수

| 함수 | 설명 |
|------|------|
| `execute_tool(name, inputs)` | Tool 이름으로 실제 함수 디스패치 |
| `run_financial_agent(query, max_turns, verbose, model)` | ReAct 루프 실행 (PII 마스킹 + Injection 탐지 내장) |
| `run_all_tests()` | 4개 테스트 케이스 자동 실행 |
| `interactive_mode()` | 대화형 입력 모드 |

### 테스트 케이스

| ID | 설명 |
|----|------|
| TC-01 | 단순 대출 계산 |
| TC-02 | 복합 질의 (대출 + 뉴스) |
| TC-03 | 신용점수 + 환율 조회 |
| TC-04 | Prompt Injection 보안 테스트 |

---

## MODULE 3: 금융 규정 RAG Q&A (`m03_memory_rag/`)

**학습 목표:** FAISS 벡터 DB 구성, HuggingFace 임베딩, MMR 검색, RAG 체인 구현

### 파이프라인 흐름

```
텍스트/PDF 입력
    → RecursiveCharacterTextSplitter (chunk_size=600, overlap=100)
    → HuggingFaceEmbeddings (multilingual-MiniLM-L12-v2)
    → FAISS 벡터 DB 저장 (로컬)
    → MMR 검색 (k=4, fetch_k=15)
    → LLM 답변 생성 (Groq llama-3.3-70b-versatile)
```

### 주요 함수

| 함수 | 설명 |
|------|------|
| `build_knowledge_base_from_text(text, save_path, ...)` | 텍스트 → FAISS 벡터 DB 생성 |
| `build_knowledge_base_from_pdf(pdf_paths, save_path)` | PDF → FAISS 벡터 DB 생성 |
| `load_knowledge_base(save_path)` | 저장된 FAISS DB 로드 |
| `create_regulation_qa_chain(vectorstore)` | LangChain RetrievalQA 체인 구성 |
| `ask_regulation(qa_chain, question)` | Q&A 실행 및 출처 반환 |
| `demo_conversation_memory()` | 대화 이력 요약 데모 |

### 내장 규정 데이터 (샘플)

- 신용대출 한도 산정 기준 (연소득 150%, 700점 이상 200%)
- DTI 기준 (일반 40%, 투기과열 30%)
- LTV 기준 (비규제 70%, 규제 50%, 투기과열 40%)
- 대출 신청 서류 및 심사 기간
- 대출 금리, 중도상환 수수료, 연체 관리

---

## MODULE 4: 여신심사 자동화 에이전트 (`m04_single_agent/`)

**학습 목표:** ReAct (Thought-Action-Observation) 루프 기반 단일 에이전트 구현

### 심사 Tool 3종

| Tool | 설명 | 주요 입력 |
|------|------|-----------|
| `extract_document_info` | 대출 신청 서류에서 정보 추출 | 케이스 ID, 서류 유형, 필드 목록 |
| `check_regulation_compliance` | DTI/LTV/나이/재직기간 규정 준수 확인 | 규정 코드, 검증 값 |
| `calculate_dti_ltv` | DTI, LTV 계산 및 통과/불통과 판정 | 연소득, 기존 채무, 대출금액, 담보가치 등 |

### 심사 규정 기준

| 항목 | 기준 |
|------|------|
| DTI | 40% 이하 (투기과열지구 30%) |
| LTV | 70% 이하 (규제지역 50%, 투기과열 40%) |
| 최소 나이 | 만 19세 이상 |
| 최소 재직기간 | 6개월 이상 |

### 에이전트 심사 순서 (6단계)

1. 신청서 기본 정보 추출
2. 신분증 정보 확인 (나이 검증)
3. 소득증빙 서류 분석
4. 담보물 평가서 확인
5. DTI / LTV 계산
6. 종합 심사 결과 판정

### 테스트 케이스

| 케이스 | 설명 | 예상 결과 |
|--------|------|-----------|
| LOAN-2025-001 | 연소득 6,000만원, 3억 대출 신청 | 승인 가능 |
| LOAN-2025-002 | 연소득 4,000만원, 4억 대출 신청 | 추가 검토 필요 |

---

## MODULE 5: 보안 & 모니터링 (`m05_monitoring/`)

**학습 목표:** LangFuse 트레이싱, PII 마스킹 테스트, Injection 탐지, 성능 지표 측정

### 주요 컴포넌트

#### `AgentMetrics` 클래스
에이전트 실행 지표 수집 (`@dataclass`)

| 속성/메서드 | 설명 |
|------------|------|
| `latency_ms` | 응답 시간 (ms) |
| `total_tokens` | 입출력 토큰 합계 |
| `estimated_cost_usd` | 토큰 단가 기반 비용 추정 ($3/M 입력, $15/M 출력) |
| `to_dict()` | 지표 딕셔너리 변환 |
| `print_summary()` | 지표 터미널 출력 |

#### `LangFuseTracer` 클래스
LangFuse 트레이싱 래퍼 (미설치 시 로컬 로깅 자동 대체)

| 메서드 | 설명 |
|--------|------|
| `start_trace(name, metadata, input)` | 트레이스 시작, trace_id 반환 |
| `start_span(name, as_type, ...)` | 스팬 생성 (context manager) |
| `record_score(trace_id, name, value)` | 점수 기록 (보안위반, 작업완료 등) |
| `update_trace_io(trace_id, input, output)` | 트레이스 I/O 업데이트 |
| `end_trace(trace_id, metrics)` | 트레이스 종료 및 flush |

#### `safe_monitored_agent_call()` — 보안 통합 에이전트 호출 흐름

```
사용자 입력
    → Prompt Injection 탐지 (위반 시 즉시 차단)
    → PII 마스킹 (개인정보 → [XXX_MASKED])
    → 에이전트 실행
    → 지표 기록 (LangFuse or 로컬 로깅)
    → (응답, AgentMetrics) 반환
```

### 테스트 시나리오

#### PII 마스킹 테스트 (7케이스)
주민등록번호, 전화번호, 계좌번호, 카드번호, 이메일, 복합 PII, 일반 텍스트

#### Prompt Injection 탐지 테스트 (8케이스)
- 공격 5종: "이전 지시 무시", "역할 변경", "시스템 프롬프트 무시", ignore previous instructions, jailbreak 등
- 정상 3종: 일반 금융 질문

#### 성능 벤치마크
P50 / P95 응답시간, 평균 토큰 수, 총 비용 및 월 예상 비용 (일 10,000건 기준) 측정

---

## 보안 설계 원칙

1. **입력 검증**: 모든 에이전트 호출 전 Prompt Injection 탐지 실행
2. **PII 보호**: 개인식별정보 5종 자동 마스킹 후 LLM 전달
3. **재시도 제한**: API 오류 시 최대 3회 지수 백오프 재시도
4. **비용 추적**: 토큰 사용량 및 예상 비용 자동 계산
5. **트레이싱**: LangFuse를 통한 에이전트 실행 이력 전체 추적

import type { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse } from 'axios'

export interface MockJobItem {
  id: string
  created_at: string
  original_file_name: string
  template_name: string
  processed_rows: number | null
  excluded_rows: number | null
  status: 'succeeded' | 'failed' | 'generating'
  result_file: {
    id: string
    is_expired: boolean
  } | null
  mappings?: {
    field_name: string
    source_column_name: string
    origin: string
  }[]
}

const mockState = {
  currentJobId: 'job-demo-2026',
  pollCount: 0,
  jobs: [
    {
      id: 'job-demo-2026',
      created_at: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      original_file_name: '2026년_상반기_매출원장.xlsx',
      template_name: '월별 영업 실적 보고서',
      processed_rows: 48,
      excluded_rows: 2,
      status: 'succeeded' as const,
      result_file: {
        id: 'file-res-demo',
        is_expired: false,
      },
      mappings: [
        { field_name: '매출일자', source_column_name: '판매일시', origin: 'ai_recommended' },
        { field_name: '거래처명', source_column_name: '업체명', origin: 'ai_recommended' },
        { field_name: '품목명', source_column_name: '상품명', origin: 'ai_recommended' },
        { field_name: '수량', source_column_name: '주문수량', origin: 'ai_recommended' },
        { field_name: '단가', source_column_name: '납품단가', origin: 'ai_recommended' },
        { field_name: '총금액', source_column_name: '공급가액', origin: 'ai_recommended' },
        { field_name: '영업담당자', source_column_name: '담당사원', origin: 'ai_recommended' },
      ],
    },
    {
      id: 'job-demo-prev',
      created_at: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
      original_file_name: '2026_08_영업실적.csv',
      template_name: '월별 영업 실적 보고서',
      processed_rows: 120,
      excluded_rows: 0,
      status: 'succeeded' as const,
      result_file: {
        id: 'file-res-prev',
        is_expired: false,
      },
      mappings: [
        { field_name: '매출일자', source_column_name: '일자', origin: 'ai_recommended' },
        { field_name: '거래처명', source_column_name: '거래처', origin: 'ai_recommended' },
        { field_name: '총금액', source_column_name: '금액', origin: 'ai_recommended' },
      ],
    },
  ] as MockJobItem[],
  templates: [
    {
      id: 1,
      name: '월별 영업 실적 보고서',
      description: '영업 부서의 월별/담당자별 매출 실적과 목표 달성률을 자동 집계하고 서식화하는 표준 템플릿입니다.',
      fields: [
        { field_key: 'sale_date', field_name: '매출일자', data_type: 'date', is_required: true, ai_hint: '거래 또는 판매 일자 (YYYY-MM-DD)' },
        { field_key: 'customer_name', field_name: '거래처명', data_type: 'string', is_required: true, ai_hint: '법인명, 고객사 상호' },
        { field_key: 'item_name', field_name: '품목명', data_type: 'string', is_required: true, ai_hint: '판매 제품 또는 용역명' },
        { field_key: 'quantity', field_name: '수량', data_type: 'integer', is_required: true, ai_hint: '판매 수량 (정수)' },
        { field_key: 'unit_price', field_name: '단가', data_type: 'decimal', is_required: false, ai_hint: '개당 단가 (원)' },
        { field_key: 'total_amount', field_name: '총금액', data_type: 'decimal', is_required: true, ai_hint: '공급가액 또는 총 거래 금액' },
        { field_key: 'sales_rep', field_name: '영업담당자', data_type: 'string', is_required: false, ai_hint: '영업 담당자 이름 또는 사번' },
      ],
    },
    {
      id: 2,
      name: '거래처별 미수금 정산 보고서',
      description: '거래처별 외상 매출 및 입금 내역, 미수 잔액을 정산하기 위한 보고서입니다.',
      fields: [
        { field_key: 'deal_date', field_name: '거래일자', data_type: 'date', is_required: true, ai_hint: '거래 기준일자' },
        { field_key: 'client_name', field_name: '거래처명', data_type: 'string', is_required: true, ai_hint: '거래처 상호' },
        { field_key: 'unpaid_amount', field_name: '미수금액', data_type: 'decimal', is_required: true, ai_hint: '미수 잔액 (원)' },
      ],
    },
  ],
}

// Router for mock endpoints
export function handleMockRoute(method: string, url: string, data?: any): any {
  // Normalize url (strip /api/v1 prefix)
  const path = url.replace(/^\/api\/v1/, '').split('?')[0]

  // Auth endpoints
  if (path === '/auth/login' || path === '/auth/signup') {
    return {
      user: {
        id: 1,
        email: data?.email || 'demo@aiexcel.com',
        name: '체험 사용자',
      },
    }
  }

  if (path === '/auth/logout') {
    return { success: true }
  }

  // File upload
  if (path === '/files/upload') {
    return {
      file_id: 'mock-file-' + Date.now(),
      file_name: 'sales_sample.csv',
      sheets: ['2026년 상반기 실적', '참고자료'],
      default_sheet: '2026년 상반기 실적',
      detected_header_row: 1,
    }
  }

  // Jobs list
  if (path === '/jobs' && method === 'GET') {
    return {
      items: mockState.jobs,
      total: mockState.jobs.length,
      page: 1,
      page_size: 20,
    }
  }

  // Create job
  if (path === '/jobs' && method === 'POST') {
    const newId = 'job-' + Math.floor(1000 + Math.random() * 9000)
    mockState.currentJobId = newId
    mockState.pollCount = 0
    return {
      job_id: newId,
      status: 'draft',
      current_step: 1,
    }
  }

  // Templates
  if (path === '/templates' && method === 'GET') {
    return {
      templates: mockState.templates,
    }
  }

  // Select template
  if (path.match(/\/jobs\/[^/]+\/template$/) && method === 'POST') {
    return { success: true }
  }

  // Step 3: Data profiling
  if (path.match(/\/jobs\/[^/]+\/data$/) && method === 'GET') {
    return {
      total_rows: 50,
      total_columns: 7,
      columns: [
        { index: 0, name: '판매일시', type: 'DATE', empty_ratio: 0, distinct: 28, samples: ['2026-03-01', '2026-03-02', '2026-03-05'] },
        { index: 1, name: '업체명', type: 'STRING', empty_ratio: 0, distinct: 14, samples: ['(주)삼성전자', '삼성전자', 'LG전자', '현대모비스'] },
        { index: 2, name: '상품명', type: 'STRING', empty_ratio: 0.02, distinct: 8, samples: ['서버 랙 A형', '네트워크 스위치 24P', '광케이블 10M'] },
        { index: 3, name: '주문수량', type: 'INTEGER', empty_ratio: 0, distinct: 12, samples: ['5', '10', '2', '20'] },
        { index: 4, name: '납품단가', type: 'DECIMAL', empty_ratio: 0.04, distinct: 15, samples: ['1,500,000', '350,000', '45,000'] },
        { index: 5, name: '공급가액', type: 'DECIMAL', empty_ratio: 0, distinct: 32, samples: ['7,500,000', '3,500,000', '900,000'] },
        { index: 6, name: '담당사원', type: 'STRING', empty_ratio: 0, distinct: 4, samples: ['김철수 대리', '이영희 과장', '박민수 팀장'] },
      ],
      warnings: [
        "3행의 '상품명' 컬럼에 빈 값이 1건 발견되었습니다.",
        "12행의 '납품단가' 컬럼에 금액 형식이 아닌 텍스트('협의')가 1건 발견되었습니다.",
      ],
    }
  }

  // Step 4: AI Mappings
  if (path.match(/\/jobs\/[^/]+\/mapping$/)) {
    if (method === 'GET') {
      return {
        source_columns: [
          { index: 0, name: '판매일시', type: 'DATE' },
          { index: 1, name: '업체명', type: 'STRING' },
          { index: 2, name: '상품명', type: 'STRING' },
          { index: 3, name: '주문수량', type: 'INTEGER' },
          { index: 4, name: '납품단가', type: 'DECIMAL' },
          { index: 5, name: '공급가액', type: 'DECIMAL' },
          { index: 6, name: '담당사원', type: 'STRING' },
        ],
        mappings: [
          { field_id: 1, field_key: 'sale_date', field_name: '매출일자', data_type: 'date', is_required: true, source_column_index: 0, confidence: 'high', reason: "컬럼명 '판매일시'와 일자 형식(YYYY-MM-DD) 일치", origin: 'ai_recommended' },
          { field_id: 2, field_key: 'customer_name', field_name: '거래처명', data_type: 'string', is_required: true, source_column_index: 1, confidence: 'high', reason: "컬럼명 '업체명' 및 법인/사업자명 샘플 데이터 패턴 일치", origin: 'ai_recommended' },
          { field_id: 3, field_key: 'item_name', field_name: '품목명', data_type: 'string', is_required: true, source_column_index: 2, confidence: 'high', reason: "컬럼명 '상품명'과 제품 키워드 일치", origin: 'ai_recommended' },
          { field_id: 4, field_key: 'quantity', field_name: '수량', data_type: 'integer', is_required: true, source_column_index: 3, confidence: 'high', reason: "'주문수량' 정수형 수치 일치", origin: 'ai_recommended' },
          { field_id: 5, field_key: 'unit_price', field_name: '단가', data_type: 'decimal', is_required: false, source_column_index: 4, confidence: 'high', reason: "'납품단가' 화폐 단위 일치", origin: 'ai_recommended' },
          { field_id: 6, field_key: 'total_amount', field_name: '총금액', data_type: 'decimal', is_required: true, source_column_index: 5, confidence: 'high', reason: "'공급가액' 컬럼과 매출 총액 의미 일치", origin: 'ai_recommended' },
          { field_id: 7, field_key: 'sales_rep', field_name: '영업담당자', data_type: 'string', is_required: false, source_column_index: 6, confidence: 'medium', reason: "'담당사원'과 이름/직급 패턴 유사", origin: 'ai_recommended' },
        ],
      }
    }
    if (method === 'POST') {
      return { success: true }
    }
  }

  // Step 5: Normalization
  if (path.match(/\/jobs\/[^/]+\/normalization$/) && method === 'GET') {
    return {
      valid_rows_count: 48,
      merge_proposals: [
        {
          id: 1,
          canonical_name: '삼성전자',
          variants: [
            { name: '(주)삼성전자', rows: 18 },
            { name: '삼성전자', rows: 8 },
            { name: 'Samsung Electronics', rows: 2 },
          ],
          is_applied: true,
        },
        {
          id: 2,
          canonical_name: 'LG전자',
          variants: [
            { name: 'LG전자(주)', rows: 12 },
            { name: '엘지전자', rows: 3 },
          ],
          is_applied: true,
        },
      ],
      error_rows: [
        { row_number: 12, column_name: '납품단가', raw_value: '협의', reason_message: '숫자 형식으로 변환할 수 없음' },
        { row_number: 34, column_name: '판매일시', raw_value: '2026/02/30', reason_message: '유효하지 않은 날짜 값 (달력에 없음)' },
      ],
    }
  }

  // Step 6: Generate
  if (path.match(/\/jobs\/[^/]+\/generate$/) && method === 'POST') {
    mockState.pollCount = 0
    return {
      job_id: mockState.currentJobId,
      status: 'generating',
    }
  }

  // Step 6: Status polling
  if (path.match(/\/jobs\/[^/]+\/status$/) && method === 'GET') {
    mockState.pollCount++
    if (mockState.pollCount <= 1) {
      return {
        status: 'generating',
        processed_rows: 25,
        excluded_rows: 0,
        result_file_id: null,
        summary: null,
        error_message: null,
      }
    }

    // Finished
    const completedJob: MockJobItem = {
      id: mockState.currentJobId,
      created_at: new Date().toISOString(),
      original_file_name: 'sales_sample.csv',
      template_name: '월별 영업 실적 보고서',
      processed_rows: 48,
      excluded_rows: 2,
      status: 'succeeded',
      result_file: {
        id: 'file-res-' + Date.now(),
        is_expired: false,
      },
      mappings: [
        { field_name: '매출일자', source_column_name: '판매일시', origin: 'ai_recommended' },
        { field_name: '거래처명', source_column_name: '업체명', origin: 'ai_recommended' },
        { field_name: '품목명', source_column_name: '상품명', origin: 'ai_recommended' },
        { field_name: '수량', source_column_name: '주문수량', origin: 'ai_recommended' },
        { field_name: '단가', source_column_name: '납품단가', origin: 'ai_recommended' },
        { field_name: '총금액', source_column_name: '공급가액', origin: 'ai_recommended' },
        { field_name: '영업담당자', source_column_name: '담당사원', origin: 'ai_recommended' },
      ],
    }

    // Add to list if not already added
    if (!mockState.jobs.find((j) => j.id === completedJob.id)) {
      mockState.jobs.unshift(completedJob)
    }

    return {
      status: 'succeeded',
      processed_rows: 48,
      excluded_rows: 2,
      result_file_id: 'file-res-demo',
      summary: {
        template_name: '월별 영업 실적 보고서',
        total_revenue: '154,200,000원',
        total_records: 48,
        merged_customers_count: 2,
        output_filename: '월별_영업_실적_보고서_20261002.xlsx',
      },
      error_message: null,
    }
  }

  // Job detail
  const detailMatch = path.match(/\/jobs\/([^/]+)$/)
  if (detailMatch) {
    const id = detailMatch[1]
    if (method === 'DELETE') {
      mockState.jobs = mockState.jobs.filter((j) => j.id !== id)
      return { success: true }
    }
    const found = mockState.jobs.find((j) => j.id === id)
    if (found) return found
    return {
      id,
      created_at: new Date().toISOString(),
      original_file_name: 'sales_sample.csv',
      template_name: '월별 영업 실적 보고서',
      processed_rows: 48,
      excluded_rows: 2,
      status: 'succeeded',
      result_file: {
        id: 'file-res-demo',
        is_expired: false,
      },
      mappings: [
        { field_name: '매출일자', source_column_name: '판매일시', origin: 'ai_recommended' },
        { field_name: '거래처명', source_column_name: '업체명', origin: 'ai_recommended' },
        { field_name: '품목명', source_column_name: '상품명', origin: 'ai_recommended' },
        { field_name: '총금액', source_column_name: '공급가액', origin: 'ai_recommended' },
      ],
    }
  }

  // Fallback
  return { success: true }
}

/**
 * Configure Axios instance to use mock responses
 */
export function setupMock(client: AxiosInstance) {
  client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
    // Override adapter for mock mode
    config.adapter = async (cfg: InternalAxiosRequestConfig): Promise<AxiosResponse> => {
      // Small simulated latency for realistic feel
      await new Promise((resolve) => setTimeout(resolve, 250))

      const method = (cfg.method || 'get').toUpperCase()
      const url = cfg.url || ''
      let data = cfg.data
      if (typeof data === 'string') {
        try {
          data = JSON.parse(data)
        } catch {
          // not json
        }
      }

      const responseBody = handleMockRoute(method, url, data)

      return {
        data: responseBody,
        status: 200,
        statusText: 'OK',
        headers: {},
        config: cfg,
      }
    }

    return config
  })
}

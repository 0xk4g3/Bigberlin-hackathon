export interface ClaimField {
  key: string
  value: string | null
}

export interface Message {
  id: string
  role: 'agent' | 'caller'
  text: string
  timestamp: string
}

export interface ClaimTicket {
  id: string
  claimRef: string
  callerName: string
  callerPhone: string
  date: string
  duration: string
  lossType: string
  location: string
  fields: ClaimField[]
  messages: Message[]
}

import { expect, test } from 'vitest'
import { clock, duration, reason } from './format'

test('clock, duration and reasons', () => {
  expect(clock(754.6)).toBe('12:34')
  expect(duration(0)).toBe('–')
  expect(reason('Target_Bombed')).toBe('Target Bombed')
})

"use client"

import * as React from "react"
import { CalendarIcon } from "lucide-react"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Input } from "@/components/ui/input"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

interface DatePickerProps {
  id?: string
  value?: string | null
  onChange: (value: string | null) => void
  disabled?: boolean
  className?: string
  min?: string
  max?: string
}

function parseIsoDate(value?: string | null): Date | undefined {
  if (!value) return undefined
  const isoMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!isoMatch) return undefined
  const [, year, month, day] = isoMatch
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  if (Number.isNaN(date.getTime())) return undefined
  if (date.getFullYear() !== Number(year)) return undefined
  if (date.getMonth() !== Number(month) - 1) return undefined
  if (date.getDate() !== Number(day)) return undefined
  return date
}

function parseDisplayDate(value?: string | null): Date | undefined {
  if (!value) return undefined
  const match = value.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (!match) return undefined

  const [, day, month, year] = match
  const date = new Date(Number(year), Number(month) - 1, Number(day))
  if (Number.isNaN(date.getTime())) return undefined
  if (date.getFullYear() !== Number(year)) return undefined
  if (date.getMonth() !== Number(month) - 1) return undefined
  if (date.getDate() !== Number(day)) return undefined
  return date
}

function formatDisplayDate(date?: Date): string {
  if (!date) return ""
  return format(date, "dd/MM/yyyy", { locale: ptBR })
}

function formatIsoDate(date?: Date): string | null {
  if (!date) return null
  return format(date, "yyyy-MM-dd")
}

function maskDateInput(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 8)
  if (digits.length <= 2) return digits
  if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`
}

function isDateWithinRange(date: Date, minDate?: Date, maxDate?: Date): boolean {
  if (minDate && date < minDate) return false
  if (maxDate && date > maxDate) return false
  return true
}

export function DatePicker({ id, value, onChange, disabled, className, min, max }: DatePickerProps) {
  const selectedDate = React.useMemo(() => parseIsoDate(value) ?? parseDisplayDate(value), [value])
  const minDate = React.useMemo(() => parseIsoDate(min), [min])
  const maxDate = React.useMemo(() => parseIsoDate(max), [max])
  const [open, setOpen] = React.useState(false)
  const [textValue, setTextValue] = React.useState(formatDisplayDate(selectedDate))
  const [month, setMonth] = React.useState<Date>(selectedDate ?? new Date())

  const disabledDays = [
    minDate ? { before: minDate } : null,
    maxDate ? { after: maxDate } : null,
  ].filter(Boolean) as Array<{ before: Date } | { after: Date }>

  React.useEffect(() => {
    const parsedFromValue = parseIsoDate(value) ?? parseDisplayDate(value)
    setTextValue(formatDisplayDate(parsedFromValue))
  }, [value])

  React.useEffect(() => {
    if (selectedDate) {
      setMonth((prev) => {
        const sameMonth =
          prev.getFullYear() === selectedDate.getFullYear() &&
          prev.getMonth() === selectedDate.getMonth()
        return sameMonth ? prev : selectedDate
      })
    }
  }, [selectedDate])

  const commitTypedValue = (typedValue: string) => {
    const trimmed = typedValue.trim()
    if (!trimmed) {
      onChange(null)
      setTextValue("")
      return
    }

    const parsed = parseDisplayDate(trimmed)
    if (!parsed || !isDateWithinRange(parsed, minDate, maxDate)) {
      setTextValue(formatDisplayDate(selectedDate))
      return
    }

    onChange(formatIsoDate(parsed))
    setTextValue(formatDisplayDate(parsed))
    setMonth(parsed)
  }

  return (
    <div className={cn("flex w-full items-center gap-2", className)}>
      <Input
        id={id}
        value={textValue}
        onChange={(e) => {
          const masked = maskDateInput(e.target.value)
          setTextValue(masked)
          if (masked.length === 10) {
            const parsed = parseDisplayDate(masked)
            if (parsed && isDateWithinRange(parsed, minDate, maxDate)) {
              onChange(formatIsoDate(parsed))
              setMonth(parsed)
            }
          }
        }}
        onBlur={() => commitTypedValue(textValue)}
        placeholder="DD/MM/YYYY"
        disabled={disabled}
        className="w-full"
        inputMode="numeric"
      />
      <Popover
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen)
          if (nextOpen && selectedDate) {
            setMonth(selectedDate)
          }
        }}
      >
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="icon"
            aria-label="Abrir calendário"
            disabled={disabled}
            className="shrink-0"
          >
            <CalendarIcon className="size-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={selectedDate}
            month={month}
            onMonthChange={setMonth}
            onSelect={(date) => {
              onChange(formatIsoDate(date))
              setTextValue(formatDisplayDate(date))
              if (date) {
                setMonth(date)
              }
              setOpen(false)
            }}
            disabled={disabledDays.length > 0 ? disabledDays : undefined}
            locale={ptBR}
            captionLayout="dropdown"
            startMonth={new Date(1900, 0, 1)}
            endMonth={new Date(new Date().getFullYear() + 1, 11, 31)}
            autoFocus
          />
        </PopoverContent>
      </Popover>
    </div>
  )
}

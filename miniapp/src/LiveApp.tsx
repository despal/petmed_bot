/**
 * Live Mini App: данные с FastAPI.
 * Auth: Telegram initData (Authorization: tma …) или DEV_TELEGRAM_ID на сервере.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, type AppointmentDto, type CareDayDto, type HouseDto, type UserDto } from './api/client'
import { BottomTabs } from './components/BottomTabs'
import { DayGrid, scrollTopForEight } from './components/DayGrid'
import { StepModal } from './components/StepModal'
import { DoneAtScreen } from './components/DoneAtScreen'
import { AnimalForm } from './components/AnimalForm'
import { AppointmentForm } from './components/AppointmentForm'
import { SettingsScreen } from './components/SettingsScreen'
import { NoAccessScreen } from './components/NoAccessScreen'
import { FirstTimezoneScreen } from './components/FirstTimezoneScreen'
import type { Overlay, TabId } from './types'

type ThemeMode = 'system' | 'light' | 'dark'

function useResolvedTheme(mode: ThemeMode) {
  const [systemDark, setSystemDark] = useState(
    () => window.matchMedia('(prefers-color-scheme: dark)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = () => setSystemDark(mq.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  if (mode === 'system') return systemDark ? 'dark' : 'light'
  return mode
}

export default function LiveApp() {
  const [bootError, setBootError] = useState<'loading' | 'forbidden' | null>('loading')
  const [user, setUser] = useState<UserDto | null>(null)
  const [house, setHouse] = useState<HouseDto | null>(null)
  const [careDay, setCareDay] = useState<CareDayDto | null>(null)
  const [appointments, setAppointments] = useState<AppointmentDto[]>([])
  const [tab, setTab] = useState<TabId>('home')
  const [tzMode, setTzMode] = useState<'house' | 'mine'>('house')
  const [overlay, setOverlay] = useState<Overlay>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [themeMode, setThemeMode] = useState<ThemeMode>(
    () => (localStorage.getItem('petmed-theme') as ThemeMode) || 'system',
  )
  const resolvedTheme = useResolvedTheme(themeMode)
  const scrollRef = useRef<HTMLDivElement>(null)

  const showToast = (msg: string) => {
    setToast(msg)
    window.setTimeout(() => setToast(null), 1800)
  }

  const refreshDay = useCallback(async () => {
    const day = await api.careDay()
    setCareDay(day)
  }, [])

  const refreshAppointments = useCallback(async () => {
    const rows = await api.appointments()
    setAppointments(rows)
  }, [])

  const refreshAfterWrite = useCallback(async () => {
    await refreshDay()
    if (tab === 'settings') await refreshAppointments()
  }, [refreshDay, refreshAppointments, tab])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolvedTheme)
  }, [resolvedTheme])

  useEffect(() => {
    localStorage.setItem('petmed-theme', themeMode)
  }, [themeMode])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const me = await api.me()
        if (cancelled) return
        setUser(me.user)
        setHouse(me.house)
        setBootError(null)
        if (me.house) {
          const day = await api.careDay()
          if (cancelled) return
          setCareDay(day)
          const rows = await api.appointments()
          if (!cancelled) setAppointments(rows)
        }
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 403) setBootError('forbidden')
        else {
          setBootError('forbidden')
          showToast(e instanceof Error ? e.message : 'Ошибка загрузки')
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const animals = careDay?.animals ?? []
  const liveAnimals = animals.filter((a) => !a.archived)
  const houseTz = house?.schedule_timezone ?? 'UTC'
  const myTz = user?.display_timezone ?? houseTz
  const displayTz = tzMode === 'house' ? houseTz : myTz

  const visibleSteps = useMemo(() => {
    const steps = careDay?.steps ?? []
    if (tab === 'home' || tab === 'settings') return steps
    if (tab.startsWith('animal:')) {
      const id = Number(tab.split(':')[1])
      return steps.filter((s) => s.animal_ids.includes(id))
    }
    return steps
  }, [careDay, tab])

  useLayoutEffect(() => {
    if (tab === 'settings' || !careDay) return
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = scrollTopForEight(visibleSteps)
  }, [tab, careDay, visibleSteps])

  if (bootError === 'loading') {
    return (
      <div className="app-root">
        <div className="centered">
          <p className="muted">Загрузка…</p>
        </div>
      </div>
    )
  }

  if (bootError === 'forbidden' || !user) {
    return (
      <div className="app-root">
        <div className="screen">
          <NoAccessScreen />
        </div>
      </div>
    )
  }

  if (!house) {
    return (
      <div className="app-root">
        <div className="screen">
          <FirstTimezoneScreen
            onConfirm={async (iana) => {
              try {
                const res = await api.createHouse(iana)
                setUser(res.user)
                setHouse(res.house)
                await refreshDay()
                await refreshAppointments()
                setTab('home')
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Не удалось создать дом')
              }
            }}
          />
          {toast && <div className="toast">{toast}</div>}
        </div>
      </div>
    )
  }

  const step =
    overlay?.type === 'step' || overlay?.type === 'done_at'
      ? careDay?.steps.find((s) => s.id === overlay.stepId)
      : undefined
  const editingAnimal =
    overlay?.type === 'animal_form' && overlay.animalId
      ? animals.find((a) => a.id === overlay.animalId)
      : undefined
  const editingAppt =
    overlay?.type === 'appointment_form' && overlay.appointmentId
      ? appointments.find((a) => a.id === overlay.appointmentId)
      : undefined

  const headerTitle = () => {
    if (tab === 'home') return 'Дом'
    if (tab === 'settings') return 'Настройки'
    if (tab.startsWith('animal:')) {
      const id = Number(tab.split(':')[1])
      return animals.find((a) => a.id === id)?.name ?? 'Животное'
    }
    return 'PetMed'
  }

  const emptyHouse = liveAnimals.length === 0
  const nowHouseLocal = new Date().toLocaleTimeString('en-GB', {
    timeZone: houseTz,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })

  return (
    <div className="app-root">
      <div className="screen">
        <header className="header">
          <h1>{headerTitle()}</h1>
          {tab !== 'settings' && (
            <div className="tz-toggle">
              <button
                type="button"
                className={tzMode === 'house' ? 'active' : ''}
                onClick={() => setTzMode('house')}
              >
                Время дома
              </button>
              <button
                type="button"
                className={tzMode === 'mine' ? 'active' : ''}
                onClick={() => setTzMode('mine')}
              >
                Моё время
              </button>
            </div>
          )}
        </header>

        <div className="main-scroll" ref={scrollRef}>
          {tab === 'settings' ? (
            <SettingsScreen
              user={user}
              house={house}
              animals={animals}
              appointments={appointments}
              theme={themeMode}
              onThemeChange={setThemeMode}
              onEditAnimal={(id) => setOverlay({ type: 'animal_form', animalId: id })}
              onAddAnimal={() => setOverlay({ type: 'animal_form' })}
              onEditAppointment={(id) =>
                setOverlay({ type: 'appointment_form', appointmentId: id })
              }
              onPickHouseTz={async (iana) => {
                try {
                  const h = await api.setHouseTz(iana)
                  setHouse(h)
                  await refreshDay()
                } catch (e) {
                  showToast(e instanceof ApiError ? e.detail : 'Ошибка')
                }
              }}
              onPickMyTz={async (iana) => {
                try {
                  const u = await api.setMyTz(iana)
                  setUser(u)
                } catch (e) {
                  showToast(e instanceof ApiError ? e.detail : 'Ошибка')
                }
              }}
            />
          ) : (
            <>
              {emptyHouse && tab === 'home' && (
                <div className="fab-inline">
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() => setOverlay({ type: 'animal_form' })}
                  >
                    Добавить животное
                  </button>
                </div>
              )}
              {!emptyHouse && tab.startsWith('animal:') && (
                <div className="fab-inline">
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() =>
                      setOverlay({
                        type: 'appointment_form',
                        presetAnimalId: Number(tab.split(':')[1]),
                      })
                    }
                  >
                    + Назначение
                  </button>
                </div>
              )}
              <DayGrid
                steps={visibleSteps}
                animals={animals}
                houseTz={houseTz}
                displayTz={displayTz}
                onOpenStep={(stepId) => setOverlay({ type: 'step', stepId })}
              />
            </>
          )}
        </div>

        <BottomTabs tab={tab} animals={animals} onChange={setTab} />

        {overlay?.type === 'step' && step && (
          <StepModal
            step={step}
            animals={animals}
            houseTz={houseTz}
            displayTz={displayTz}
            onClose={() => setOverlay(null)}
            onDone={async () => {
              try {
                await api.mark(step.id, 'done')
                setOverlay(null)
                await refreshAfterWrite()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
            onDoneAt={() => setOverlay({ type: 'done_at', stepId: step.id })}
            onSkip={async () => {
              try {
                await api.mark(step.id, 'skipped')
                setOverlay(null)
                await refreshAfterWrite()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
            onEdit={() =>
              setOverlay({
                type: 'appointment_form',
                appointmentId: step.appointment_id,
              })
            }
            onDisable={async () => {
              try {
                await api.archiveAppointment(step.appointment_id)
                setOverlay(null)
                await refreshAfterWrite()
                await refreshAppointments()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
          />
        )}

        {overlay?.type === 'done_at' && step && (
          <DoneAtScreen
            step={step}
            nowHouseLocal={nowHouseLocal}
            onBack={() => setOverlay({ type: 'step', stepId: step.id })}
            onConfirm={async (hm) => {
              try {
                await api.mark(step.id, 'done_at', hm)
                setOverlay(null)
                await refreshAfterWrite()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
          />
        )}

        {overlay?.type === 'animal_form' && (
          <AnimalForm
            animal={editingAnimal}
            usedKeys={animals.map((a) => a.avatar_key).filter(Boolean) as string[]}
            onClose={() => setOverlay(null)}
            onSave={async (name, avatarKey) => {
              try {
                if (editingAnimal) {
                  await api.patchAnimal(editingAnimal.id, {
                    name,
                    avatar_key: avatarKey,
                  })
                } else {
                  await api.addAnimal(name, avatarKey)
                }
                setOverlay(null)
                await refreshAfterWrite()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
          />
        )}

        {overlay?.type === 'appointment_form' && (
          <AppointmentForm
            appointment={editingAppt}
            animals={animals}
            appointments={appointments}
            presetAnimalId={overlay.presetAnimalId}
            onClose={() => setOverlay(null)}
            onSave={async (payload) => {
              try {
                if (editingAppt) {
                  const { kind: _k, animal_ids: _a, ...patch } = payload
                  await api.patchAppointment(editingAppt.id, patch)
                } else {
                  await api.createAppointment(payload)
                }
                setOverlay(null)
                await refreshAfterWrite()
                await refreshAppointments()
              } catch (e) {
                showToast(e instanceof ApiError ? e.detail : 'Ошибка')
              }
            }}
          />
        )}

        {toast && <div className="toast">{toast}</div>}
      </div>
    </div>
  )
}

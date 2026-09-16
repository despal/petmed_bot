import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react'
import { StandSwitcher } from './components/StandSwitcher'
import { NoAccessScreen } from './components/NoAccessScreen'
import { FirstTimezoneScreen } from './components/FirstTimezoneScreen'
import { BottomTabs } from './components/BottomTabs'
import { DayGrid, scrollTopForEight } from './components/DayGrid'
import { StepModal } from './components/StepModal'
import { DoneAtScreen } from './components/DoneAtScreen'
import { AnimalForm } from './components/AnimalForm'
import { AppointmentForm } from './components/AppointmentForm'
import { SettingsScreen } from './components/SettingsScreen'
import { cloneStand } from './data/stands'
import type { Overlay, StandId, TabId } from './types'

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

export default function App() {
  const [standId, setStandId] = useState<StandId>('full_day')
  const [data, setData] = useState(() => cloneStand('full_day'))
  const [tab, setTab] = useState<TabId>('home')
  const [tzMode, setTzMode] = useState<'house' | 'mine'>('house')
  const [overlay, setOverlay] = useState<Overlay>(null)
  const [toast, setToast] = useState<string | null>(null)
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => {
    return (localStorage.getItem('petmed-theme') as ThemeMode) || 'system'
  })
  const resolvedTheme = useResolvedTheme(themeMode)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolvedTheme)
  }, [resolvedTheme])

  useEffect(() => {
    localStorage.setItem('petmed-theme', themeMode)
  }, [themeMode])

  const switchStand = (id: StandId) => {
    setStandId(id)
    setData(cloneStand(id))
    setOverlay(null)
    setTzMode('house')
    if (id === 'settings') setTab('settings')
    else setTab('home')
  }

  const showToast = (msg: string) => {
    setToast(msg)
    window.setTimeout(() => setToast(null), 1800)
  }

  const houseTz = data.house?.schedule_timezone ?? 'UTC'
  const myTz = data.user?.display_timezone ?? houseTz
  const displayTz = tzMode === 'house' ? houseTz : myTz

  const animals = data.careDay?.animals ?? []
  const liveAnimals = animals.filter((a) => !a.archived)

  const visibleSteps = useMemo(() => {
    const steps = data.careDay?.steps ?? []
    if (tab === 'home' || tab === 'settings') return steps
    if (tab.startsWith('animal:')) {
      const id = Number(tab.split(':')[1])
      return steps.filter((s) => s.animal_ids.includes(id))
    }
    return steps
  }, [data.careDay, tab])

  useLayoutEffect(() => {
    if (tab === 'settings' || !data.careDay) return
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = scrollTopForEight(visibleSteps)
  }, [standId, tab, data.careDay, visibleSteps])

  const patchStepStatus = (
    stepId: number,
    status: 'done' | 'skipped' | 'pending' | 'overdue',
  ) => {
    setData((prev) => {
      if (!prev.careDay) return prev
      return {
        ...prev,
        careDay: {
          ...prev.careDay,
          steps: prev.careDay.steps.map((s) =>
            s.id === stepId ? { ...s, status } : s,
          ),
        },
      }
    })
  }

  const headerTitle = () => {
    if (tab === 'home') return 'Дом'
    if (tab === 'settings') return 'Настройки'
    if (tab.startsWith('animal:')) {
      const id = Number(tab.split(':')[1])
      return animals.find((a) => a.id === id)?.name ?? 'Животное'
    }
    return 'PetMed'
  }

  const renderMain = () => {
    if (!data.user) return <NoAccessScreen />

    if (!data.house) {
      return (
        <FirstTimezoneScreen
          onConfirm={(iana) => {
            setData((prev) => ({
              ...prev,
              user: prev.user
                ? { ...prev.user, display_timezone: iana }
                : prev.user,
              house: {
                id: 1,
                creator_user_id: prev.user!.id,
                schedule_timezone: iana,
                doubler_user_id: null,
              },
              careDay: {
                id: 1,
                house_id: 1,
                plan_date: '2026-09-15',
                starts_at: '2026-09-14T21:00:00Z',
                ends_at: '2026-09-15T21:00:00Z',
                steps: [],
                animals: [],
              },
              appointments: [],
            }))
            setTab('home')
            showToast('Дом создан (мок)')
          }}
        />
      )
    }

    const emptyHouse = liveAnimals.length === 0

    return (
      <div className="main-scroll" ref={scrollRef}>
        {tab === 'settings' ? (
          <SettingsScreen
            user={data.user}
            house={data.house}
            animals={animals}
            appointments={data.appointments}
            theme={themeMode}
            onThemeChange={setThemeMode}
            onEditAnimal={(id) =>
              setOverlay({ type: 'animal_form', animalId: id })
            }
            onAddAnimal={() => setOverlay({ type: 'animal_form' })}
            onEditAppointment={(id) =>
              setOverlay({ type: 'appointment_form', appointmentId: id })
            }
            onPickHouseTz={(iana) =>
              setData((prev) =>
                prev.house
                  ? {
                      ...prev,
                      house: { ...prev.house, schedule_timezone: iana },
                    }
                  : prev,
              )
            }
            onPickMyTz={(iana) =>
              setData((prev) =>
                prev.user
                  ? {
                      ...prev,
                      user: { ...prev.user, display_timezone: iana },
                    }
                  : prev,
              )
            }
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
              nowHouseLocal={data.nowHouseLocal}
              onOpenStep={(stepId) => setOverlay({ type: 'step', stepId })}
            />
          </>
        )}
      </div>
    )
  }

  const step =
    overlay?.type === 'step' || overlay?.type === 'done_at'
      ? data.careDay?.steps.find((s) => s.id === overlay.stepId)
      : undefined

  const editingAnimal =
    overlay?.type === 'animal_form' && overlay.animalId
      ? animals.find((a) => a.id === overlay.animalId)
      : undefined

  const editingAppt =
    overlay?.type === 'appointment_form' && overlay.appointmentId
      ? data.appointments.find((a) => a.id === overlay.appointmentId)
      : undefined

  const showChrome = Boolean(data.user && data.house)

  return (
    <div className="app-root">
      <StandSwitcher standId={standId} onChange={switchStand} />
      <div className="screen">
        {showChrome && (
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
        )}

        {renderMain()}

        {showChrome && (
          <BottomTabs
            tab={tab}
            animals={animals}
            onChange={setTab}
            showAddAnimal={false}
          />
        )}

        {overlay?.type === 'step' && step && (
          <StepModal
            step={step}
            animals={animals}
            houseTz={houseTz}
            displayTz={displayTz}
            onClose={() => setOverlay(null)}
            onDone={() => {
              patchStepStatus(step.id, 'done')
              setOverlay(null)
              showToast('Отмечено выполненным (мок)')
            }}
            onDoneAt={() => setOverlay({ type: 'done_at', stepId: step.id })}
            onSkip={() => {
              patchStepStatus(step.id, 'skipped')
              setOverlay(null)
              showToast('Пропущено (мок)')
            }}
            onEdit={() =>
              setOverlay({
                type: 'appointment_form',
                appointmentId: step.appointment_id,
              })
            }
            onDisable={() => {
              setOverlay(null)
              showToast('Выключить — мок, без записи')
            }}
          />
        )}

        {overlay?.type === 'done_at' && step && (
          <DoneAtScreen
            step={step}
            nowHouseLocal={data.nowHouseLocal}
            onBack={() => setOverlay({ type: 'step', stepId: step.id })}
            onConfirm={(hm) => {
              patchStepStatus(step.id, 'done')
              setOverlay(null)
              showToast(`Выполнено в ${hm} (мок)`)
            }}
          />
        )}

        {overlay?.type === 'animal_form' && (
          <AnimalForm
            animal={editingAnimal}
            usedKeys={animals
              .map((a) => a.avatar_key)
              .filter(Boolean) as string[]}
            onClose={() => setOverlay(null)}
            onSave={(name, avatarKey) => {
              setOverlay(null)
              showToast(
                editingAnimal
                  ? `Сохранено: ${name} (${avatarKey}) — мок`
                  : `Добавлено: ${name} — мок, без записи`,
              )
            }}
          />
        )}

        {overlay?.type === 'appointment_form' && data.house && (
          <AppointmentForm
            appointment={editingAppt}
            animals={animals}
            appointments={data.appointments}
            presetAnimalId={overlay.presetAnimalId}
            onClose={() => setOverlay(null)}
            onSave={(_payload) => {
              setOverlay(null)
              showToast('Сохранено (мок, без записи в день)')
            }}
          />
        )}

        {toast && <div className="toast">{toast}</div>}
      </div>
    </div>
  )
}

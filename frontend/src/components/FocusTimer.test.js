import React, { act } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import FocusTimer from './FocusTimer';
import { getFocusStats, saveFocusSession } from '../http/api';

jest.mock('../http/api', () => ({
  saveFocusSession: jest.fn(() => Promise.resolve({ ok: true })),
  getFocusStats: jest.fn(() => Promise.resolve({ today: { sessions: 0, minutes: 0 }, week: { sessions: 0, minutes: 0 } })),
}));

jest.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    t: {
      focusTitle: 'Focus timer',
      focusSubtitle: 'Run one short session on the task that matters now.',
      focusSessions: 'Sessions',
      focusMinutes: 'Minutes',
      focusCustom: 'Custom',
      focusSelectTask: 'Select a task',
      focusNoTask: 'No task',
      focusWorkPhase: 'Focus',
      focusBreakPhase: 'Break',
      focusStart: 'Start',
      focusResume: 'Resume',
      focusPause: 'Pause',
      focusReset: 'Reset',
      focusCompleted: 'Focus complete',
      focusSaveFailed: 'Save failed',
      focusSoundOn: 'Sound on',
      focusSoundOff: 'Sound off',
    },
  }),
}));

describe('FocusTimer', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    window.sessionStorage.clear();
    jest.clearAllMocks();
    saveFocusSession.mockResolvedValue({ ok: true });
    getFocusStats.mockResolvedValue({ today: { sessions: 0, minutes: 0 }, week: { sessions: 0, minutes: 0 } });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('restores paused remaining time after remount instead of resetting to preset duration', async () => {
    window.sessionStorage.setItem(
      'daymark_focus_timer_v2',
      JSON.stringify({
        presetIndex: 0,
        customWork: 25,
        customBreak: 5,
        useCustom: false,
        phase: 'work',
        remainingSeconds: 1200,
        isRunning: false,
        targetEpochMs: null,
        sessionCount: 1,
        soundEnabled: true,
        selectedTaskId: 7,
      })
    );

    render(
      <FocusTimer
        tasks={[{ id: 7, title: 'Write thesis' }]}
        selectedTaskId={7}
        onSelectedTaskChange={jest.fn()}
        compact
      />
    );

    await waitFor(() => {
      expect(screen.getByText('20:00')).toBeInTheDocument();
    });

    expect(screen.queryByText('25:00')).not.toBeInTheDocument();
  });

  it('records a completed session and falls back to a taskless save when the task link is stale', async () => {
    jest.setSystemTime(new Date('2026-03-14T12:00:00.000Z'));
    saveFocusSession
      .mockRejectedValueOnce(Object.assign(new Error('Task not found'), { status: 404 }))
      .mockResolvedValueOnce({ ok: true });
    getFocusStats.mockResolvedValue({ today: { sessions: 1, minutes: 1 }, week: { sessions: 1, minutes: 1 } });

    window.sessionStorage.setItem(
      'daymark_focus_timer_v2',
      JSON.stringify({
        presetIndex: 0,
        customWork: 1,
        customBreak: 5,
        useCustom: true,
        phase: 'work',
        remainingSeconds: 1,
        isRunning: true,
        targetEpochMs: Date.now() + 1000,
        sessionCount: 0,
        soundEnabled: false,
        savedWorkMinutes: 0,
        selectedTaskId: 7,
      })
    );

    render(
      <FocusTimer
        tasks={[{ id: 7, title: 'Write thesis' }]}
        selectedTaskId={7}
        onSelectedTaskChange={jest.fn()}
        compact
      />
    );

    await act(async () => {
      jest.advanceTimersByTime(1200);
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(saveFocusSession).toHaveBeenNthCalledWith(1, 7, 1, 'work');
      expect(saveFocusSession).toHaveBeenNthCalledWith(2, null, 1, 'work');
      expect(screen.getByText('Focus complete')).toBeInTheDocument();
    });
  });

  it('keeps the current remaining time after pausing', async () => {
    jest.setSystemTime(new Date('2026-03-14T12:00:00.000Z'));

    render(
      <FocusTimer
        tasks={[{ id: 7, title: 'Write thesis' }]}
        selectedTaskId={7}
        onSelectedTaskChange={jest.fn()}
        compact
      />
    );

    fireEvent.click(screen.getByText('Start'));

    await act(async () => {
      jest.advanceTimersByTime(65 * 1000);
      await Promise.resolve();
    });

    fireEvent.click(screen.getByText('Pause'));

    await waitFor(() => {
      expect(screen.getByText('23:55')).toBeInTheDocument();
      expect(screen.getByText('Resume')).toBeInTheDocument();
    });

    expect(screen.queryByText('25:00')).not.toBeInTheDocument();
  });
});

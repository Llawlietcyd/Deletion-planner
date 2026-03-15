import React, { act } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import DailyPlan from './DailyPlan';
import { deleteTask, getTasks, updateTask } from '../http/api';

jest.mock('../http/api', () => ({
  getTasks: jest.fn(),
  updateTask: jest.fn(),
  deleteTask: jest.fn(),
}));

jest.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    lang: 'zh',
    t: {
      todayPlanTitle: '今日计划',
      todayPlanSubtitle: '把今天过清楚',
      taskKindDaily: '每日',
      taskKindWeekly: '每周',
      taskKindTemporary: '临时',
      loadingTasks: '加载中',
      todayPlanEmpty: '空',
      btnDefer: '推迟',
      deleteBtn: '删除',
      btnDone: '完成',
      focusAction: '专注',
    },
  }),
}));

jest.mock('./FocusTimer', () => function FocusTimer() {
  return <div data-testid="focus-timer" />;
});

jest.mock('./InspirationBox', () => function InspirationBox() {
  return <div data-testid="inspiration-box" />;
});

describe('DailyPlan', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-03-15T00:30:00.000Z'));
    getTasks.mockResolvedValue([
      {
        id: 1,
        title: 'Write recap',
        description: '',
        category: 'unclassified',
        status: 'active',
        priority: 1,
        sort_order: 0,
        deferral_count: 0,
        completion_count: 0,
        source: 'manual',
        task_kind: 'daily',
        recurrence_weekday: null,
        decision_reason: '',
        completed_at: null,
        deleted_at: null,
        due_date: null,
        created_at: '2026-03-14T10:00:00+00:00',
        updated_at: '2026-03-14T10:00:00+00:00',
      },
    ]);
    updateTask.mockResolvedValue({
      id: 1,
      title: 'Write recap',
      description: '',
      category: 'unclassified',
      status: 'active',
      priority: 1,
      sort_order: 0,
      deferral_count: 0,
      completion_count: 1,
      source: 'manual',
      task_kind: 'daily',
      recurrence_weekday: null,
      decision_reason: 'Recurring task completed for this cycle by user.',
      completed_at: '2026-03-15T00:30:00+00:00',
      deleted_at: null,
      due_date: null,
      created_at: '2026-03-14T10:00:00+00:00',
      updated_at: '2026-03-15T00:30:00+00:00',
    });
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllMocks();
    window.sessionStorage.clear();
  });

  it('keeps recurring tasks marked complete when the completion timestamp is UTC-next-day but still today in Eastern time', async () => {
    render(<DailyPlan />);

    const taskTitle = await screen.findByText('Write recap');
    const taskRow = taskTitle.closest('.daily-log-row');
    const checkbox = taskRow?.querySelector('.daily-log-check');

    expect(taskRow).toBeTruthy();
    expect(checkbox).toBeTruthy();

    await act(async () => {
      fireEvent.click(checkbox);
    });

    await waitFor(() => {
      expect(updateTask).toHaveBeenCalledWith(1, { status: 'completed' });
      expect(screen.getByRole('button', { name: '完成' })).toHaveClass('checked');
      expect(screen.getByText('Write recap')).toHaveClass('line-through');
    });
  });

  it('hides a deferred daily task until tomorrow', async () => {
    updateTask.mockResolvedValueOnce({
      id: 1,
      title: 'Write recap',
      description: '',
      category: 'unclassified',
      status: 'active',
      priority: 1,
      sort_order: 0,
      deferral_count: 1,
      completion_count: 0,
      source: 'manual',
      task_kind: 'daily',
      recurrence_weekday: null,
      decision_reason: 'Task deferred to 2026-03-15 by user (total deferrals: 1).',
      completed_at: null,
      deleted_at: null,
      due_date: '2026-03-15',
      created_at: '2026-03-14T10:00:00+00:00',
      updated_at: '2026-03-15T00:30:00+00:00',
    });

    render(<DailyPlan />);

    const deferButton = await screen.findByText('推迟');

    await act(async () => {
      fireEvent.click(deferButton);
    });

    await waitFor(() => {
      expect(updateTask).toHaveBeenCalledWith(1, { deferral_count_delta: 1, due_date: '2026-03-15' });
      expect(screen.queryByText('Write recap')).not.toBeInTheDocument();
    });
  });

  it('permanently deletes a task from the current board', async () => {
    deleteTask.mockResolvedValueOnce({ message: 'Task permanently deleted', task_id: 1 });

    render(<DailyPlan />);

    const deleteButton = await screen.findByText('删除');

    await act(async () => {
      fireEvent.click(deleteButton);
    });

    await waitFor(() => {
      expect(deleteTask).toHaveBeenCalledWith(1, true);
      expect(screen.queryByText('Write recap')).not.toBeInTheDocument();
    });
  });
});

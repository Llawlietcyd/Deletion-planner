import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import { render, screen, waitFor } from '@testing-library/react';
import ReviewPage from './ReviewPage';

jest.mock('../http/api', () => ({
  getHistory: jest.fn(() => Promise.resolve([])),
  getTasks: jest.fn(() => Promise.resolve([])),
  getMoodHistory: jest.fn(() => Promise.resolve([])),
  getFocusHistory: jest.fn(() => Promise.resolve([])),
  getReviewInsights: jest.fn(() => Promise.resolve({ daily: '', weekly: '', monthly: '' })),
  getWeeklySummary: jest.fn(() => Promise.resolve({ summary: '' })),
}));

jest.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    lang: 'zh',
    t: {
      loadingHistory: '加载中',
      reviewTitle: '复盘',
      navSettings: '设置',
      taskKindTemporary: '临时',
      taskKindWeekly: '每周',
    },
  }),
}));

const { getTasks } = require('../http/api');

describe('ReviewPage', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date('2026-03-24T12:00:00.000Z'));
    jest.clearAllMocks();
    getTasks.mockResolvedValue([
      {
        id: 7,
        title: '每周二要去打工',
        task_kind: 'weekly',
        recurrence_weekday: 1,
        due_date: null,
      },
    ]);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('does not add a calendar plan badge for recurring tasks alone', async () => {
    render(
      <MemoryRouter>
        <ReviewPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('每周二要去打工')).toBeInTheDocument();
    });

    expect(screen.queryByText('计划 1')).not.toBeInTheDocument();
  });

  it('keeps the calendar plan badge for one-off scheduled tasks', async () => {
    getTasks.mockResolvedValue([
      {
        id: 8,
        title: '给女朋友过生日',
        task_kind: 'temporary',
        due_date: '2026-03-24',
      },
    ]);

    render(
      <MemoryRouter>
        <ReviewPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('给女朋友过生日')).toBeInTheDocument();
    });

    expect(screen.getAllByText('计划 1').length).toBeGreaterThan(0);
  });
});

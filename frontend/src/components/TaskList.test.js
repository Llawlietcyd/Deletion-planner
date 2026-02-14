import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import TaskList from './TaskList';

jest.mock('../http/api', () => ({
  deleteTask: jest.fn(),
  updateTask: jest.fn(),
}));

jest.mock('../i18n/LanguageContext', () => ({
  useLanguage: () => ({
    t: {
      catCore: 'Core',
      catDeferrable: 'Deferrable',
      catDeletion: 'Delete?',
      catUnclassified: 'Unclassified',
      priorityLow: 'Low',
      priorityMedium: 'Medium',
      priorityHigh: 'High',
      priorityUrgent: 'Urgent',
      deferred: 'Deferred',
      completed: 'Completed',
      noTasks: 'No tasks yet',
      noTasksSub: 'Add some tasks',
      permanentDeleteConfirm: 'confirm',
      deleteConfirm: 'confirm',
      completeConfirm: 'confirm',
      markCompletedBtn: 'Mark as completed',
      btnDone: 'Done',
      deleteBtn: 'Delete',
      permanentDeleteBtn: 'Delete Forever',
    },
  }),
}));

describe('TaskList', () => {
  beforeEach(() => {
    window.confirm = jest.fn(() => true);
  });

  it('renders quick action buttons for active tasks', () => {
    render(
      <TaskList
        tasks={[{ id: 1, title: 'Task A', category: 'core', priority: 0, deferral_count: 0, completion_count: 0 }]}
        filter="active"
        onRefresh={jest.fn()}
      />
    );

    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('Delete')).toBeInTheDocument();
  });
});

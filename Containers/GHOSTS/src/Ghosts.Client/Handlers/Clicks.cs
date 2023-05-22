﻿// Copyright 2017 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using Ghosts.Domain;
using Ghosts.Domain.Code;

namespace Ghosts.Client.Handlers
{
    public class Clicks : BaseHandler
    {
        [DllImport("user32.dll", CharSet = CharSet.Auto, CallingConvention = CallingConvention.StdCall)]
        public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint cButtons, uint dwExtraInfo);

        //Mouse actions
        private const int MouseeventfLeftdown = 0x02;
        private const int MouseeventfLeftup = 0x04;

        //if we wanted to add right click events
        //private const int MOUSEEVENTF_RIGHTDOWN = 0x08;
        //private const int MOUSEEVENTF_RIGHTUP = 0x10;

        public Clicks(TimelineHandler handler)
        {
            base.Init(handler);
            Log.Trace("Spawning mouse click handler...");

            try
            {
                if (handler.Loop)
                {
                    while (true)
                    {
                        Ex(handler);
                    }
                }
                else
                {
                    Ex(handler);
                }
            }
            catch (Exception e)
            {
                Log.Error(e);
            }
        }

        public void Ex(TimelineHandler handler)
        {
            foreach (var timelineEvent in handler.TimeLineEvents)
            {
                Infrastructure.WorkingHours.Is(handler);

                if (timelineEvent.DelayBefore > 0)
                    Thread.Sleep(timelineEvent.DelayBefore);

                Log.Trace($"Click: {timelineEvent.Command} with delay after of {timelineEvent.DelayAfter}");

                switch (timelineEvent.Command)
                {
                    default:
                        //Call the imported function with the cursor's current position
                        var x = Cursor.Position.X;
                        var y = Cursor.Position.Y;

                        DoLeftMouseClick(x, y);
                        Log.Trace($"Click: {x}:{y}");

                        Thread.Sleep(Jitter.Randomize(timelineEvent.CommandArgs[0], timelineEvent.CommandArgs[1], timelineEvent.CommandArgs[2]));
                        this.Report(handler.HandlerType.ToString(), timelineEvent.Command, "", timelineEvent.TrackableId, $"{x}:{y}");
                        break;
                }

                if (timelineEvent.DelayAfter > 0)
                    Thread.Sleep(timelineEvent.DelayAfter);
            }
        }

        private static void DoLeftMouseClick(int x, int y)
        {
            mouse_event(MouseeventfLeftdown | MouseeventfLeftup, (uint)x, (uint)y, 0, 0);
        }
    }
}
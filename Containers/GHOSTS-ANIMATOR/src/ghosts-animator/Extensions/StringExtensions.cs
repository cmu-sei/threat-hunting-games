﻿// Copyright 2020 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace Ghosts.Animator.Extensions
{
    public static class StringExtensions
    {
        public static string Numerify(this string number_string)
        {
            return number_string.Replace('#', () => AnimatorRandom.Rand.Next(10).ToString().ToCharArray()[0]);
        }

        public static string Letterify(this string letter_string)
        {
            return letter_string.Replace('?', () => 'a'.To('z').RandomElement());
        }

        public static string Bothify(this string str)
        {
            return Letterify(Numerify(str));
        }
        
        private static string Replace(this string str, char item, Func<char> character)
        {
            var builder = new StringBuilder(str.Length);

            foreach (var c in str.ToCharArray())
            {
                builder.Append(c == item ? character() : c);
            }

            return builder.ToString();
        }

        public static string ToAccountSafeString(this string o)
        {
            o = Regex.Replace(o, @"[^0-9a-zA-Z\._]", "");
            return o;
        }

        public static string After(this string value, string a)
        {
            var posA = value.LastIndexOf(a, StringComparison.InvariantCultureIgnoreCase);
            if (posA == -1)
            {
                return "";
            }
            var adjustedPosA = posA + a.Length;
            return adjustedPosA >= value.Length ? "" : value.Substring(adjustedPosA);
        }
        
        private static IEnumerable<char> To(this char from, char to)
        {
            for(var i = from; i <= to; i++) {
                yield return i;
            }
        }
        
        public static IEnumerable<string> ReadAndFilter(this FileInfo info, Predicate<string> condition)
        {
            using (var reader = new StreamReader(info.FullName))
            {
                string line;
                while ((line = reader.ReadLine()) != null)
                {
                    if (condition(line))
                    {
                        yield return line;
                    }
                }
            }
        }
    }
}

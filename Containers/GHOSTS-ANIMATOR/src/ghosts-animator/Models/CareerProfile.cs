// Copyright 2020 Carnegie Mellon University. All Rights Reserved. See LICENSE.md file for terms.

using System.Collections.Generic;

namespace Ghosts.Animator.Models
{
    public class CareerProfile
    {
        public int WorkEthic { get; set; }
        public int TeamValue { get; set; }
        public IEnumerable<StrengthProfile> Strengths { get; set; }
        public IEnumerable<WeaknessProfile> Weaknesses { get; set; }

        public CareerProfile()
        {
            this.Strengths = new List<StrengthProfile>();
            this.Weaknesses = new List<WeaknessProfile>();
        }

        public class StrengthProfile
        {
            public int Id { get; set; }
            public string Name { get; set; }
        }

        public class WeaknessProfile
        {
            public int Id { get; set; }
            public string Name { get; set; }
        }
    }
}
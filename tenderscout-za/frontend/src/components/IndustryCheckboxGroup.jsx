// components/IndustryCheckboxGroup.jsx
// Reusable multi‑select checkbox group for the 20 standard industry categories.
// Fetches the list of valid industries from the API on mount, then renders a
// grid of checkboxes. The parent controls the selected list via `selected` and
// `onChange` props.

import React from 'react';

const IndustryCheckboxGroup = ({ selected, onChange }) => {
  // Local state for the full list of industries loaded from the API
  const [industries, setIndustries] = React.useState([]);

  // Load industries once when the component mounts
  React.useEffect(() => {
    // Dynamic import to avoid circular dependencies; the API module
    // calls GET /user/industries (public endpoint).
    import('../api/industries').then(mod => mod.fetchIndustries().then(setIndustries));
  }, []);

  // Toggle an industry: if already selected, remove it; otherwise add it.
  const toggle = (industry) => {
    if (selected.includes(industry)) {
      onChange(selected.filter(s => s !== industry));
    } else {
      onChange([...selected, industry]);
    }
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
      {industries.map(ind => (
        <label key={ind} className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={selected.includes(ind)}
            onChange={() => toggle(ind)}
            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
          />
          {ind}
        </label>
      ))}
    </div>
  );
};

export default IndustryCheckboxGroup;
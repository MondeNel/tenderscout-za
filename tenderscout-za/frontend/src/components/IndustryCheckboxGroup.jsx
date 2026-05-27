import React from 'react';

const IndustryCheckboxGroup = ({ selected, onChange }) => {
  const [industries, setIndustries] = React.useState([]);

  React.useEffect(() => {
    import('../api/industries').then(mod => mod.fetchIndustries().then(setIndustries));
  }, []);

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

use hashbrown::HashTable;
use pyo3::prelude::*;

struct Slot {
    hash: u64,
    obj: PyObject,
}

#[derive(Default)]
pub struct PyIndexSet {
    lookup: HashTable<usize>,
    objects: Vec<Slot>,
}

impl PyIndexSet {
    pub fn get_index(&self, index: usize) -> Option<&PyObject> {
        self.objects.get(index).map(|slot| &slot.obj)
    }

    pub fn get_full(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<(usize, &PyObject)>> {
        let hash = obj.hash()? as u64;

        let mut res = Ok(());

        let index = self.lookup.find(hash, |&index| {
            if res.is_err() {
                false
            } else {
                match self.objects[index].obj.bind(obj.py()).eq(obj) {
                    Ok(is_eq) => is_eq,
                    Err(err) => {
                        res = Err(err);
                        false
                    }
                }
            }
        });

        res?;

        Ok(index.map(|&index| (index, &self.objects[index].obj)))
    }

    pub fn insert_full(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<(usize, bool)> {
        let hash = obj.hash()? as u64;

        let mut res = Ok(());

        let entry = self.lookup.entry(
            hash,
            |&index| {
                if res.is_err() {
                    false
                } else {
                    match self.objects[index].obj.bind(obj.py()).eq(obj) {
                        Ok(is_eq) => is_eq,
                        Err(err) => {
                            res = Err(err);
                            false
                        }
                    }
                }
            },
            |&index| self.objects[index].hash,
        );

        res?;

        match entry {
            hashbrown::hash_table::Entry::Occupied(entry) => Ok((*entry.get(), false)),
            hashbrown::hash_table::Entry::Vacant(entry) => {
                let index = self.objects.len();
                self.objects.push(Slot { hash, obj: obj.clone().unbind() });
                entry.insert(index);

                Ok((index, true))
            }
        }
    }
}
